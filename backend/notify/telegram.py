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


async def send_document(bot: Bot, chat_id: int, file_path: str, caption: str = "") -> bool:
    """Envía un archivo desde el disco. Devuelve True si se entregó."""
    try:
        from pathlib import Path
        with open(file_path, "rb") as f:
            await bot.send_document(
                chat_id=chat_id,
                document=f,
                caption=caption,
            )
        return True
    except Exception as exc:  # noqa: BLE001 - notificar sin tumbar el flujo
        logger.error("No se pudo enviar archivo a chat %s: %s", chat_id, exc)
        return False


async def send_document_bytes(bot: Bot, chat_id: int, filename: str, data: bytes, caption: str = "") -> bool:
    """Envía unos bytes como documento sin tocar el disco (los backups se
    descifran en memoria antes de enviarse). Devuelve True si se entregó."""
    import io
    try:
        await bot.send_document(
            chat_id=chat_id,
            document=io.BytesIO(data),
            filename=filename,
            caption=caption,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - notificar sin tumbar el flujo
        logger.error("No se pudo enviar archivo a chat %s: %s", chat_id, exc)
        return False


async def notify_admins(text: str) -> None:
    """Envía una alerta de seguridad a los administradores de Telegram.

    Usa el token del .env directamente (sin depender de la Application del bot)
    para poder usarse desde cualquier parte del proceso.
    """
    from core.config import settings
    from services import users as users_srv

    admins = users_srv.list_admin_chat_ids()
    if not admins:
        logger.info("Alerta de seguridad sin destinatarios (no hay admins de Telegram): %s", text)
        return
    bot = Bot(token=settings().bot_token)
    for chat_id in admins:
        try:
            await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
        except Exception as exc:  # noqa: BLE001
            logger.error("No se pudo notificar alerta al chat %s: %s", chat_id, exc)