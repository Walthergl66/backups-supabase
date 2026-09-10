"""Comandos que no encajan en los demás: /cancel y mensajes sin comando."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.common import UNAUTHORIZED_TEXT, _authorized_user
from notify import telegram as notify_mod

logger = logging.getLogger(__name__)


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    await notify_mod.send_message(context.bot, chat_id, "Operación cancelada.")
    context.user_data.pop("addbd_projects", None)
    context.user_data.pop("addbd_selected", None)
    context.user_data.pop("addbd_slug", None)
    context.user_data.pop("addbd_connection", None)
    return ConversationHandler.END


async def _cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Devuelve el chat_id del usuario en el propio chat.

    Funciona también para chats no registrados: es la forma de obtener tu
    chat_id para darlo de alta desde la web sin necesidad de revisar logs.
    """
    chat_id = update.effective_chat.id
    await notify_mod.send_message(
        context.bot, chat_id, f"Tu chat ID es: {chat_id}"
    )


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