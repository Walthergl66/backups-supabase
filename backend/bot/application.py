"""Construcción e inicio de la aplicación del bot de Telegram.

Wiring de todos los handlers (comandos directos y conversaciones) dentro de
un único `Application` de python-telegram-bot, más el bucle de polling que se
corre como task asyncio compartiendo el loop de la web.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers import addbd, basics, backup_cmd, misc, register, status_cmd
from core.config import settings

logger = logging.getLogger(__name__)


def build_application() -> Application:
    app = Application.builder().token(settings().bot_token).build()

    app.add_handler(register.build_conversation())
    app.add_handler(addbd.build_conversation())
    app.add_handler(CommandHandler("start", basics._cmd_start))
    app.add_handler(CommandHandler("help", basics._cmd_start))
    app.add_handler(CommandHandler("proyectos", basics._cmd_proyectos))
    app.add_handler(CommandHandler("backup", backup_cmd._cmd_backup))
    app.add_handler(CommandHandler("status", status_cmd._cmd_status))
    app.add_handler(CommandHandler("historial", status_cmd._cmd_historial))
    app.add_handler(CommandHandler("id", misc._cmd_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, misc._on_other))
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