"""Bot de Telegram para backups y monitoreo de Supabase.

Comandos:
  /register              -> auto-registro con PAT de Supabase
  /addbd                 -> agregar BD desde proyectos de Supabase
  /proyectos             -> lista los proyectos activos conectados
  /backup <slug>         -> dispara un backup bajo demanda
  /status <slug>         -> estado de conexión y Management API
  /historial <slug>      -> últimos backups del proyecto
  /cancel                -> cancela el flujo conversacional activo

Flujo de validación (por comando):
  1. chat_id del mensaje.
  2. Si no está en `users` (o está inactivo): respuesta genérica de
     "no autorizado", sin revelar si el proyecto existe.
  3. Comprobación del permiso concreto (can_backup / can_monitor).
  4. Ejecución y registro en audit_log.
"""

from __future__ import annotations

import asyncio
import logging
import re

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backup import monitor as monitor_mod
from backup import runner as backup_runner
from core.config import settings
from notify import telegram as notify_mod
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv
from services import supabase_api as api_srv
from services import users as users_srv

logger = logging.getLogger(__name__)

UNAUTHORIZED_TEXT = ("No autorizado. Si crees que esto es un error, "
                     "contacta al administrador del sistema.")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Estados para ConversationHandler
REG_PAT, ADD_BD_SELECT, ADD_BD_SLUG, ADD_BD_CONNECTION = range(4)


# ----------------------------------------------------------------------
# Helpers de validación y formato
# ----------------------------------------------------------------------

def _authorized_user(chat_id: int) -> dict | None:
    user = users_srv.authorized_chat(chat_id)
    if user is None:
        logger.info("Chat no registrado intentó usar el bot: chat_id=%s", chat_id)
    return user


def _project_for_action(slug: str) -> dict | None:
    project = projects_srv.get_by_slug(slug.strip())
    if project is None or not project["activo"]:
        return None
    return project


def _split(text: str, chunk: int = 3800) -> list[str]:
    if len(text) <= chunk:
        return [text]
    parts: list[str] = []
    while text:
        parts.append(text[:chunk])
        text = text[chunk:]
    return parts


def _fmt_size(size: float | None) -> str:
    if size is None:
        return "desconocido"
    if size >= 1e6:
        return f"{size / 1e6:.2f} MB"
    if size >= 1e3:
        return f"{size / 1e3:.1f} KB"
    return f"{size:.0f} B"


def _ensure_user(chat_id: int, username: str | None = None) -> dict | None:
    """Devuelve el usuario si existe, o lo crea con rol 'usuario'."""
    user = users_srv.authorized_chat(chat_id)
    if user is not None:
        return user
    nombre = username or f"Telegram {chat_id}"
    try:
        users_srv.create_user(chat_id, nombre, rol="usuario")
        return users_srv.authorized_chat(chat_id)
    except users_srv.UserError:
        return None


# ----------------------------------------------------------------------
# Comandos existentes
# ----------------------------------------------------------------------

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return
    has_pat = users_srv.has_pat(chat_id)
    pat_info = "\n/register - registrar tu PAT de Supabase" if not has_pat else ""
    addbd_info = "\n/addbd - agregar BD desde tu cuenta de Supabase" if has_pat else ""
    text = (
        "Hola {nombre}. Este bot gestiona backups de Supabase.\n\n"
        "Comandos disponibles:\n"
        "{pat_info}"
        "{addbd_info}"
        "/proyectos - proyectos activos conectados\n"
        "/backup <slug> - respaldo bajo demanda de un proyecto\n"
        "/status <slug> - estado del proyecto (DB y Management API)\n"
        "/historial <slug> - últimos backups del proyecto"
    ).format(nombre=user["nombre"], pat_info=pat_info, addbd_info=addbd_info)
    await notify_mod.send_message(context.bot, chat_id, text)


async def _cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    projects = projects_srv.list_projects(only_active=True)

    if users_srv.has_pat(chat_id):
        account = users_srv.find_account_by_chat_id(chat_id)
        if account:
            projects = [p for p in projects if p["account_id"] == account["id"]]

    if not projects:
        await notify_mod.send_message(
            context.bot, chat_id, "No hay proyectos activos conectados todavía."
        )
        return
    lines = [f"Proyectos activos ({len(projects)}):", ""]
    for p in projects:
        ultimo = p.get("ultimo_backup") or "sin backups"
        lines.append(f"• {p['slug']} — último backup: {ultimo}")
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))
    audit_srv.log_action("bot_proyectos", "ok", user_id=user["id"])


async def _cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    args = context.args or []
    if not args:
        await notify_mod.send_message(
            context.bot, chat_id, "Uso: /backup <slug> — indica el proyecto a respaldar."
        )
        return

    slug = args[0]
    project = _project_for_action(slug)
    if project is None:
        audit_srv.log_action("bot_backup_intento", "error", user_id=user["id"],
                             detalle=f"slug={slug} no existe o inactivo")
        await notify_mod.send_message(context.bot, chat_id, "Proyecto no encontrado o inactivo.")
        return

    if not users_srv.can(user["id"], project["id"], "can_backup"):
        audit_srv.log_action("bot_backup", "error", user_id=user["id"], project_id=project["id"],
                             detalle="permiso can_backup denegado")
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    await notify_mod.send_message(
        context.bot, chat_id, f"Iniciando backup de '{project['slug']}'…"
    )
    full_project = projects_srv.get_project(project["id"], include_secret=True)
    result = await asyncio.to_thread(backup_runner.run_backup, full_project)

    if result.ok:
        detail = (
            f"Backup completado\n"
            f"• Proyecto: {project['slug']}\n"
            f"• Tamaño: {_fmt_size(result.tamaño_archivo)}\n"
            f"• Duración: {result.duracion_seg:.1f}s\n"
            f"• Ubicación: {result.ruta_archivo}"
        )
        if result.archivos_eliminados:
            detail += f"\n• Rotación: se eliminaron {len(result.archivos_eliminados)} backup(s) antiguo(s)"
        history_srv.record(
            project["id"], "ok",
            tamaño_archivo=result.tamaño_archivo,
            ruta_archivo=result.ruta_archivo,
            detalle=result.detalle,
        )
        audit_srv.log_action("bot_backup", "ok", user_id=user["id"], project_id=project["id"],
                             detalle=result.detalle)
    else:
        detail = f"Backup fallido\n• Proyecto: {project['slug']}\n• Motivo: {result.detalle}"
        history_srv.record(project["id"], "error", detalle=result.detalle)
        audit_srv.log_action("bot_backup", "error", user_id=user["id"], project_id=project["id"],
                             detalle=result.detalle)
    for msg in _split(detail):
        await notify_mod.send_message(context.bot, chat_id, msg)


async def _cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    args = context.args or []
    if not args:
        await notify_mod.send_message(
            context.bot, chat_id, "Uso: /status <slug> — indica el proyecto a consultar."
        )
        return

    slug = args[0]
    project = _project_for_action(slug)
    if project is None:
        await notify_mod.send_message(context.bot, chat_id, "Proyecto no encontrado o inactivo.")
        return

    if not users_srv.can(user["id"], project["id"], "can_monitor"):
        audit_srv.log_action("bot_status", "error", user_id=user["id"], project_id=project["id"],
                             detalle="permiso can_monitor denegado")
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    audit_srv.log_action("bot_status", "ok", user_id=user["id"], project_id=project["id"])
    full_project = projects_srv.get_project(project["id"], include_secret=True)
    pat = accounts_srv.get_plaintext_pat(project["account_id"])

    db_ok, db_msg = await asyncio.to_thread(
        monitor_mod.check_database_connection, full_project["connection_plain"]
    )
    api_ok, api_msg = await asyncio.to_thread(
        monitor_mod.check_supabase_api, project["project_ref"], pat
    )
    lines = [
        f"Estado de '{project['slug']}':",
        f"• Conexión DB: {'OK' if db_ok else 'FALLO'}\n  {db_msg}",
        f"• Management API: {'OK' if api_ok else 'FALLO'}\n  {api_msg}",
    ]
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))


async def _cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    args = context.args or []
    if not args:
        await notify_mod.send_message(
            context.bot, chat_id, "Uso: /historial <slug> — indica el proyecto a consultar."
        )
        return

    slug = args[0]
    project = _project_for_action(slug)
    if project is None:
        await notify_mod.send_message(context.bot, chat_id, "Proyecto no encontrado o inactivo.")
        return

    if not users_srv.can(user["id"], project["id"], "can_monitor"):
        audit_srv.log_action("bot_historial", "error", user_id=user["id"], project_id=project["id"],
                             detalle="permiso can_monitor denegado")
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    audit_srv.log_action("bot_historial", "ok", user_id=user["id"], project_id=project["id"])
    rows = history_srv.recent(project["id"], limit=10)
    if not rows:
        await notify_mod.send_message(
            context.bot, chat_id, f"Aún no hay backups registrados para '{project['slug']}'."
        )
        return
    lines = [f"Últimos backups de '{project['slug']}':", ""]
    for r in rows:
        estado = "OK" if r["resultado"] == "ok" else "FALLO"
        lines.append(f"• {r['fecha']} — {estado} ({_fmt_size(r['tamaño_archivo'])})")
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))


# ----------------------------------------------------------------------
# /register — Auto-registro con PAT de Supabase
# ----------------------------------------------------------------------

async def _register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return ConversationHandler.END

    if users_srv.has_pat(chat_id):
        await notify_mod.send_message(
            context.bot, chat_id,
            "Ya tienes un PAT registrado. Si necesitas actualizarlo, "
            "usa /register de nuevo."
        )

    await notify_mod.send_message(
        context.bot, chat_id,
        "Envía tu Personal Access Token de Supabase.\n"
        "Lo puedes encontrar en: Supabase Dashboard > Account > Access Tokens\n\n"
        "⚠️ Este token se almacenará cifrado de forma segura."
    )
    return REG_PAT


async def _register_pat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    pat = update.message.text.strip()

    await notify_mod.send_message(context.bot, chat_id, "Validando PAT…")

    ok, msg = await asyncio.to_thread(api_srv.validate_pat, pat)
    if not ok:
        await notify_mod.send_message(
            context.bot, chat_id,
            f"El PAT no es válido: {msg}\n\n"
            "Verifica que lo hayas copiado correctamente e intenta de nuevo con /register."
        )
        return ConversationHandler.END

    users_srv.save_pat(chat_id, pat)

    try:
        projects = await asyncio.to_thread(api_srv.list_projects, pat)
    except Exception as exc:
        logger.warning("Error al listar proyectos: %s", exc)
        await notify_mod.send_message(
            context.bot, chat_id,
            "PAT registrado correctamente, pero no pude listar tus proyectos.\n"
            "Usa /addbd más tarde para agregar un proyecto."
        )
        return ConversationHandler.END

    if not projects:
        await notify_mod.send_message(
            context.bot, chat_id,
            "PAT registrado correctamente.\n"
            "No se encontraron proyectos en tu cuenta de Supabase."
        )
        return ConversationHandler.END

    lines = ["PAT registrado correctamente.\n", "Tus proyectos en Supabase:", ""]
    for i, p in enumerate(projects, 1):
        lines.append(f"{i}. {p['name']} ({p['ref'][:8]}…) — {p['status']}")
    lines.append("\nUsa /addbd para agregar un proyecto como base de datos del bot.")

    audit_srv.log_action("bot_register", "ok", user_id=update.effective_user.id or 0,
                         detalle=f"chat_id={chat_id}, {len(projects)} proyectos")
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))
    return ConversationHandler.END


# ----------------------------------------------------------------------
# /addbd — Agregar BD desde proyectos de Supabase
# ----------------------------------------------------------------------

async def _addbd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return ConversationHandler.END

    if not users_srv.has_pat(chat_id):
        await notify_mod.send_message(
            context.bot, chat_id,
            "Primero debes registrar tu PAT con /register."
        )
        return ConversationHandler.END

    pat = users_srv.get_pat(chat_id)
    await notify_mod.send_message(context.bot, chat_id, "Obteniendo tus proyectos de Supabase…")

    try:
        all_projects = await asyncio.to_thread(api_srv.list_projects, pat)
    except Exception as exc:
        logger.warning("Error al listar proyectos: %s", exc)
        await notify_mod.send_message(
            context.bot, chat_id, "No pude obtener tus proyectos. Intenta más tarde."
        )
        return ConversationHandler.END

    account = users_srv.find_account_by_chat_id(chat_id)
    existing_refs = set()
    if account:
        all_db_projects = projects_srv.list_projects(only_active=False)
        existing_refs = {
            p["project_ref"] for p in all_db_projects
            if p["account_id"] == account["id"]
        }

    available = [p for p in all_projects if p["ref"] not in existing_refs]

    if not available:
        await notify_mod.send_message(
            context.bot, chat_id,
            "No hay proyectos nuevos disponibles.\n"
            "Todos tus proyectos de Supabase ya están registrados en el sistema."
        )
        return ConversationHandler.END

    context.user_data["addbd_projects"] = available

    lines = ["Proyectos disponibles en tu cuenta de Supabase:", ""]
    for i, p in enumerate(available, 1):
        lines.append(f"{i}. {p['name']} ({p['ref'][:8]}…) — {p['status']}")
    lines.append("\nSelecciona un proyecto (número):")

    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))
    return ADD_BD_SELECT


async def _addbd_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    try:
        idx = int(text) - 1
    except ValueError:
        await notify_mod.send_message(
            context.bot, chat_id, "Envía un número de la lista."
        )
        return ADD_BD_SELECT

    projects = context.user_data.get("addbd_projects", [])
    if idx < 0 or idx >= len(projects):
        await notify_mod.send_message(
            context.bot, chat_id, f"Número inválido. Elige entre 1 y {len(projects)}."
        )
        return ADD_BD_SELECT

    selected = projects[idx]
    context.user_data["addbd_selected"] = selected

    await notify_mod.send_message(
        context.bot, chat_id,
        f"Proyecto seleccionado: {selected['name']}\n"
        f"Ref: {selected['ref']}\n\n"
        "Envía un slug para usar en comandos del bot.\n"
        "Solo minúsculas, números, guiones o guiones bajos.\n"
        "Ejemplo: mi_app_prod"
    )
    return ADD_BD_SLUG


async def _addbd_slug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    slug = update.message.text.strip()

    if not _SLUG_RE.match(slug):
        await notify_mod.send_message(
            context.bot, chat_id,
            "Slug inválido. Usa solo minúsculas, números, guiones o guiones bajos "
            "(debe empezar por letra o número)."
        )
        return ADD_BD_SLUG

    existing = projects_srv.get_by_slug(slug)
    if existing is not None:
        await notify_mod.send_message(
            context.bot, chat_id,
            f"Ya existe un proyecto con el slug '{slug}'. Elige otro."
        )
        return ADD_BD_SLUG

    context.user_data["addbd_slug"] = slug
    selected = context.user_data["addbd_selected"]

    pat = users_srv.get_pat(chat_id)
    await notify_mod.send_message(context.bot, chat_id, "Obteniendo cadena de conexión…")

    connection = await asyncio.to_thread(api_srv.get_connection_string, pat, selected["ref"])

    if connection:
        context.user_data["addbd_connection"] = connection
        await _create_project_from_selection(update, context)
        return ConversationHandler.END

    await notify_mod.send_message(
        context.bot, chat_id,
        "No pude obtener la cadena de conexión automáticamente.\n"
        "Envía la cadena de conexión (pooler) desde el Dashboard de Supabase:\n"
        "Project Settings > Database > Connection string > Transaction mode\n\n"
        "Ejemplo: postgresql://postgres.xxx:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    return ADD_BD_CONNECTION


async def _addbd_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    connection = update.message.text.strip()

    if not connection.startswith("postgresql://"):
        await notify_mod.send_message(
            context.bot, chat_id,
            "La cadena de conexión debe empezar con 'postgresql://'.\n"
            "Intenta de nuevo."
        )
        return ADD_BD_CONNECTION

    context.user_data["addbd_connection"] = connection
    await _create_project_from_selection(update, context)
    return ConversationHandler.END


async def _create_project_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    selected = context.user_data["addbd_selected"]
    slug = context.user_data["addbd_slug"]
    connection = context.user_data["addbd_connection"]

    account = users_srv.find_account_by_chat_id(chat_id)
    if account is None:
        account_name = f"Telegram: {chat_id}"
        account_id = accounts_srv.create_account(account_name, users_srv.get_pat(chat_id))
    else:
        account_id = account["id"]

    try:
        project_id = projects_srv.create_project(
            slug=slug,
            nombre=selected["name"],
            account_id=account_id,
            connection=connection,
            project_ref=selected["ref"],
        )
    except projects_srv.ProjectError as exc:
        await notify_mod.send_message(context.bot, chat_id, f"Error al crear el proyecto: {exc}")
        return

    if user:
        users_srv.upsert_permission(user["id"], project_id, can_backup=True, can_monitor=True)

    audit_srv.log_action("bot_addbd", "ok", user_id=user["id"] if user else 0,
                         project_id=project_id,
                         detalle=f"slug='{slug}', ref='{selected['ref']}'")

    await notify_mod.send_message(
        context.bot, chat_id,
        f"Proyecto '{slug}' registrado correctamente.\n\n"
        f"Ya puedes usar:\n"
        f"• /backup {slug} — respaldar\n"
        f"• /status {slug} — verificar estado\n"
        f"• /historial {slug} — ver historial"
    )

    context.user_data.pop("addbd_projects", None)
    context.user_data.pop("addbd_selected", None)
    context.user_data.pop("addbd_slug", None)
    context.user_data.pop("addbd_connection", None)


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    await notify_mod.send_message(context.bot, chat_id, "Operación cancelada.")
    context.user_data.pop("addbd_projects", None)
    context.user_data.pop("addbd_selected", None)
    context.user_data.pop("addbd_slug", None)
    context.user_data.pop("addbd_connection", None)
    return ConversationHandler.END


# ----------------------------------------------------------------------
# Mensajes sin comando
# ----------------------------------------------------------------------

async def _on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensajes que no son comandos: registro el chat_id para poder dar de
    alta al usuario desde la interfaz web, sin revelar nada en el chat."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.full_name
    user = _authorized_user(chat_id)
    if user is None:
        logger.info("Intento de uso del bot desde chat no registrado (chat_id=%s, username=%s)",
                    chat_id, username)
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return
    await notify_mod.send_message(
        context.bot, chat_id,
        "Usa /start para ver los comandos disponibles."
    )


# ----------------------------------------------------------------------
# Construcción e inicio
# ----------------------------------------------------------------------

def build_application() -> Application:
    app = Application.builder().token(settings().bot_token).build()

    register_conv = ConversationHandler(
        entry_points=[CommandHandler("register", _register_start)],
        states={
            REG_PAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _register_pat)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
    )

    addbd_conv = ConversationHandler(
        entry_points=[CommandHandler("addbd", _addbd_start)],
        states={
            ADD_BD_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_select)],
            ADD_BD_SLUG: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_slug)],
            ADD_BD_CONNECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_connection)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
    )

    app.add_handler(register_conv)
    app.add_handler(addbd_conv)
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_start))
    app.add_handler(CommandHandler("proyectos", _cmd_proyectos))
    app.add_handler(CommandHandler("backup", _cmd_backup))
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("historial", _cmd_historial))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_other))
    return app


async def run_bot_forever(app: Application) -> None:
    """Inicia el polling del bot dentro del loop compartido con la web.

    Corre como una task asyncio adicional; se detiene al cancelar la task
    (p. ej. cuando uvicorn acaba la vida del servidor).
    """
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot de Telegram activo (polling iniciado).")
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
