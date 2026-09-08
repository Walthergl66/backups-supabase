"""Bot de Telegram para backups y monitoreo de Supabase.

Comandos:
  /proyectos                -> lista los proyectos activos conectados
  /backup <slug>            -> dispara un backup bajo demanda
  /status <slug>            -> estado de conexión y Management API
  /historial <slug>         -> últimos backups del proyecto

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

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from backup import monitor as monitor_mod
from backup import runner as backup_runner
from core.config import settings
from notify import telegram as notify_mod
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv
from services import users as users_srv

logger = logging.getLogger(__name__)

UNAUTHORIZED_TEXT = ("No autorizado. Si crees que esto es un error, "
                     "contacta al administrador del sistema.")


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


# ----------------------------------------------------------------------
# Comandos
# ----------------------------------------------------------------------

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return
    text = (
        "Hola {nombre}. Este bot gestiona backups de Supabase.\n\n"
        "Comandos disponibles:\n"
        "/proyectos - proyectos activos conectados\n"
        "/backup <slug> - respaldo bajo demanda de un proyecto\n"
        "/status <slug> - estado del proyecto (DB y Management API)\n"
        "/historial <slug> - últimos backups del proyecto"
    ).format(nombre=user["nombre"])
    await notify_mod.send_message(context.bot, chat_id, text)


async def _cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return
    projects = projects_srv.list_projects(only_active=True)
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
        # La validación del slug contra la whitelist se hace MÁS arriba: nunca
        # pasamos un slug arbitrario a subprocess.
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