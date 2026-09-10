"""Flujo conversacional /register: auto-registro con PAT de Supabase."""

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

from bot.handlers.common import _auth_or_deny
from bot.handlers.misc import _cancel
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import supabase_api as api_srv
from services import users as users_srv

logger = logging.getLogger(__name__)

REG_PAT = 1


def build_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("register", _register_start)],
        states={
            REG_PAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _register_pat)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
    )


async def _register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
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