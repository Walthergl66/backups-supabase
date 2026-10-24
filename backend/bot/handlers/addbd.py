"""Flujo conversacional /addbd: agregar una base de datos.

Soporta dos caminos:
- **Supabase**: importa un proyecto con el PAT del usuario y obtiene la
  cadena de conexión automáticamente (o la pide si la API falla).
- **PostgreSQL directo**: pide una URI, valida y prueba la conexión antes de
  guardar el proyecto.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.common import SLUG_RE, _auth_or_deny
from bot.handlers.misc import _cancel
from notify import telegram as notify_mod
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import projects as projects_srv
from services import providers
from services import supabase_api as api_srv
from services import users as users_srv

logger = logging.getLogger(__name__)

<<<<<<< HEAD
ADD_BD_PROVIDER, ADD_BD_SELECT, ADD_BD_CONNECTION, ADD_BD_SLUG = range(1, 5)

_CONNECTION_HELP = (
    "Envía la cadena de conexión de PostgreSQL.\n"
    "Formato: postgresql://usuario:contraseña@host:5432/basedatos\n\n"
    "Consejos:\n"
    "• Añade ?sslmode=require si el servidor exige SSL.\n"
    "• Usa una conexión directa (sin túneles SSH).\n"
    "• El mensaje con la cadena se borrará del chat tras leerlo."
)
=======
ADD_BD_SELECT, ADD_BD_SLUG, ADD_BD_CONNECTION = range(1, 4)
ADD_BD_PASSWORD = 4

# Marcador con el que Supabase devuelve la connection string sin contraseña.
_PASSWORD_MARKER = "[YOUR-PASSWORD]"
>>>>>>> origin/main


def build_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("addbd", _addbd_start)],
        states={
            ADD_BD_PROVIDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_provider)],
            ADD_BD_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_select)],
            ADD_BD_CONNECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_connection)],
<<<<<<< HEAD
            ADD_BD_SLUG: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_slug)],
=======
            ADD_BD_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_password)],
>>>>>>> origin/main
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
    )


async def _delete_message(update: Update) -> None:
    """Borra el mensaje del usuario para no dejar credenciales en el chat."""
    try:
        await update.message.delete()
    except Exception as exc:  # noqa: BLE001 - el bot puede no tener permiso
        logger.debug("No se pudo borrar el mensaje con credenciales: %s", exc)


async def _addbd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return ConversationHandler.END

    context.user_data.clear()
    await notify_mod.send_message(
        context.bot, chat_id,
        "¿De dónde sale la base de datos que quieres respaldar?\n\n"
        "1. Supabase (importar un proyecto de tu cuenta)\n"
        "2. PostgreSQL directo (cadena de conexión)\n\n"
        "Envía 1 o 2."
    )
    return ADD_BD_PROVIDER


async def _addbd_provider(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    choice = update.message.text.strip()

    if choice == "1":
        return await _addbd_supabase(update, context)
    if choice == "2":
        context.user_data["addbd_mode"] = "postgres"
        await notify_mod.send_message(context.bot, chat_id, _CONNECTION_HELP)
        return ADD_BD_CONNECTION

    await notify_mod.send_message(context.bot, chat_id, "Envía 1 (Supabase) o 2 (PostgreSQL directo).")
    return ADD_BD_PROVIDER


async def _addbd_supabase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lista los proyectos de Supabase que aún no están registrados."""
    chat_id = update.effective_chat.id
    if not users_srv.has_pat(chat_id):
        await notify_mod.send_message(
            context.bot, chat_id,
            "Para importar desde Supabase primero registra tu PAT con /register.\n"
            "Si prefieres una base propia, usa la opción 2."
        )
        return ADD_BD_PROVIDER

    context.user_data["addbd_mode"] = "supabase"
    pat = users_srv.get_pat(chat_id)
    await notify_mod.send_message(context.bot, chat_id, "Obteniendo tus proyectos de Supabase…")

    try:
        all_projects = await asyncio.to_thread(api_srv.list_projects, pat)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de la API
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
    context.user_data["addbd_nombre"] = selected["name"]

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

    if not SLUG_RE.match(slug):
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

    if context.user_data.get("addbd_mode") == "postgres":
        connection = context.user_data.get("addbd_connection")
        if connection:
            return await _create_project(update, context, connection)
        return await _create_direct_project(update, context)

    selected = context.user_data["addbd_selected"]
    pat = users_srv.get_pat(chat_id)
    await notify_mod.send_message(context.bot, chat_id, "Obteniendo cadena de conexión…")

    connection = await asyncio.to_thread(api_srv.get_connection_string, pat, selected["ref"])

    if connection:
<<<<<<< HEAD
        return await _create_project(update, context, connection)
=======
        if _PASSWORD_MARKER in connection:
            context.user_data["addbd_connection"] = connection
            await notify_mod.send_message(
                context.bot, chat_id,
                "Supabase entregó la cadena con [YOUR-PASSWORD].\n"
                "Envía la contraseña de la BD del proyecto:\n"
                "(se guardará, cifrada, dentro de la cadena de conexión)"
            )
            return ADD_BD_PASSWORD
        context.user_data["addbd_connection"] = connection
        await _create_project_from_selection(update, context)
        return ConversationHandler.END
>>>>>>> origin/main

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
    await _delete_message(update)

    ok, detail = providers.postgres.validate_dsn(connection)
    if not ok:
        await notify_mod.send_message(
            context.bot, chat_id, f"Cadena de conexión inválida: {detail}\n\n{_CONNECTION_HELP}"
        )
        return ADD_BD_CONNECTION

    await notify_mod.send_message(context.bot, chat_id, "Probando la conexión…")
    result = await asyncio.to_thread(providers.postgres.test_connection, connection)
    if not result.ok:
        await notify_mod.send_message(
            context.bot, chat_id,
            f"No se pudo conectar: {result.detalle}\n\nRevisa los datos y envía la cadena de nuevo."
        )
        return ADD_BD_CONNECTION

    if _PASSWORD_MARKER in connection:
        context.user_data["addbd_connection"] = connection
        await notify_mod.send_message(
            context.bot, chat_id,
            "La cadena incluye [YOUR-PASSWORD].\n"
            "Envía la contraseña de la BD:\n"
            "(se guardará, cifrada, dentro de la cadena de conexión)"
        )
        return ADD_BD_PASSWORD

    context.user_data["addbd_connection"] = connection
    context.user_data.setdefault(
        "addbd_nombre", result.database or "PostgreSQL directo"
    )
    extra = f" (PostgreSQL {result.server_version})" if result.server_version else ""
    await notify_mod.send_message(
        context.bot, chat_id, f"Conexión verificada con {result.database}{extra}."
    )

    if context.user_data.get("addbd_slug"):
        return await _create_project(update, context, connection)

    await notify_mod.send_message(
        context.bot, chat_id,
        "Envía un slug para usar en comandos del bot.\n"
        "Solo minúsculas, números, guiones o guiones bajos.\n"
        f"Ejemplo: {projects_srv.slugify(result.database or 'mi_base') or 'mi_base'}"
    )
    return ADD_BD_SLUG


<<<<<<< HEAD
async def _create_direct_project(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Un proyecto PostgreSQL directo aún no tiene conexión: se pide ahora."""
    chat_id = update.effective_chat.id
    await notify_mod.send_message(context.bot, chat_id, _CONNECTION_HELP)
    return ADD_BD_CONNECTION


async def _create_project(
    update: Update, context: ContextTypes.DEFAULT_TYPE, connection: str
) -> int:
=======
async def _addbd_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    password = update.message.text.strip()
    if not password:
        await notify_mod.send_message(
            context.bot, chat_id,
            "La contraseña no puede estar vacía. Envíala de nuevo o usa /cancel."
        )
        return ADD_BD_PASSWORD

    connection = context.user_data.get("addbd_connection", "")
    final_connection = api_srv._inject_password(connection, password)
    if not final_connection or _PASSWORD_MARKER in final_connection:
        await notify_mod.send_message(
            context.bot, chat_id,
            "No pude insertar la contraseña en la cadena de conexión. "
            "Revisa el formato e inténtalo de nuevo o usa /cancel."
        )
        return ADD_BD_PASSWORD

    context.user_data["addbd_connection"] = final_connection
    await _create_project_from_selection(update, context)
    return ConversationHandler.END


async def _create_project_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
>>>>>>> origin/main
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return ConversationHandler.END

    mode = context.user_data.get("addbd_mode") or "supabase"
    slug = context.user_data["addbd_slug"]
    nombre = context.user_data.get("addbd_nombre") or slug
    selected = context.user_data.get("addbd_selected") or {}

    if mode == "supabase":
        account = users_srv.find_account_by_chat_id(chat_id)
        if account is None:
            account_id = accounts_srv.create_account(
                f"Telegram: {chat_id}", users_srv.get_pat(chat_id) or "", provider="supabase"
            )
        else:
            account_id = account["id"]
        project_ref = selected.get("ref") or ""
        provider = "supabase"
    else:
        # Los proyectos directos usan el grupo por defecto del sistema.
        account_id = None
        project_ref = ""
        provider = "postgres"

    try:
        project_id = projects_srv.create_project(
            slug=slug,
            nombre=nombre,
            account_id=account_id,
            connection=connection,
            project_ref=project_ref,
            provider=provider,
        )
    except projects_srv.ProjectError as exc:
        await notify_mod.send_message(context.bot, chat_id, f"Error al crear el proyecto: {exc}")
        return ConversationHandler.END

    users_srv.upsert_permission(user["id"], project_id, can_backup=True, can_monitor=True)
    audit_srv.log_action(
        "bot_addbd", "ok", user_id=user["id"], project_id=project_id,
        detalle=f"slug='{slug}', provider='{provider}', ref='{project_ref}'",
    )

    await notify_mod.send_message(
        context.bot, chat_id,
        f"Proyecto '{slug}' registrado correctamente.\n\n"
        f"Ya puedes usar:\n"
        f"• /test {slug} — probar la conexión\n"
        f"• /backup {slug} — respaldar\n"
        f"• /status {slug} — verificar estado\n"
        f"• /historial {slug} — ver historial"
    )

    context.user_data.clear()
    return ConversationHandler.END
