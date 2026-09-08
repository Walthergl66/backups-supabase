"""Canales de notificación.

Canal principal: respuesta directa en el chat de Telegram que originó la
acción. (El respaldo por correo vía Resend se dejó fuera a petición del
cliente en esta versión.)
"""

from __future__ import annotations

import logging

from telegram import Bot

logger = logging.getLogger(__name__)


async def send_message(bot: Bot, chat_id: int, text: str) -> bool:
    """Envía un mensaje de texto. Devuelve True si se entregó."""
    try:
        await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
        return True
    except Exception as exc:  # noqa: BLE001 - notificar sin tumbar el flujo
        logger.error("No se pudo notificar al chat %s: %s", chat_id, exc)
        return False