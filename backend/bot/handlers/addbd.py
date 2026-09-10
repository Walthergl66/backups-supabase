"""Flujo conversacional /addbd: agregar una BD desde proyectos de Supabase."""

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
from services import supabase_api as api_srv
from services import users as users_srv

logger = logging.getLogger(__name__)

ADD_BD_SELECT, ADD_BD_SLUG, ADD_BD_CONNECTION = range(1, 4)


def build_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("addbd", _addbd_start)],
        states={
            ADD_BD_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_select)],
            ADD_BD_SLUG: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_slug)],
            ADD_BD_CONNECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, _addbd_connection)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
    )


async def _addbd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
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
    user = await _auth_or_deny(update, context)
    if user is None:
        return
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