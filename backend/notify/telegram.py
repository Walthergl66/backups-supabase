"""Canales de notificación.

Canal principal: respuesta directa en el chat de Telegram que originó la
acción. (El respaldo por correo vía Resend se dejó fuera a petición del
cliente en esta versión.)
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Bot

from core import sanitize

logger = logging.getLogger(__name__)

# Límite de Telegram por mensaje (caracteres). Por encima hay que trocear.
_MAX_TEXT = 4096


def _chunks(text: str, limit: int = _MAX_TEXT) -> list[str]:
    """Divide un texto en fragmentos <= limit sin cortar líneas a la mitad."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.split("\n"):
        if current and current_len + len(line) + 1 > limit:
            parts.append("\n".join(current))
            current, current_len = [], 0
        if len(line) > limit:
            # Una línea única más larga que el límite (p. ej. un stacktrace):
            # se corta sin importar las líneas.
            if current:
                parts.append("\n".join(current))
                current, current_len = [], 0
            for i in range(0, len(line), limit):
                parts.append(line[i : i + limit])
            continue
        current.append(line)
        current_len += len(line) + 1
    if current:
        parts.append("\n".join(current))
    return parts or [text]


async def send_message(bot: Bot, chat_id: int, text: str) -> bool:
    """Envía un mensaje de texto, troceándolo si supera los 4096 caracteres."""
    ok = True
    for part in _chunks(text):
        try:
            await bot.send_message(chat_id=chat_id, text=sanitize.redact_secrets(part),
                                   disable_web_page_preview=True)
        except Exception as exc:  # noqa: BLE001 - notificar sin tumbar el flujo
            logger.error("No se pudo notificar al chat %s: %s", chat_id, exc)
            ok = False
    return ok


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
        for part in _chunks(text):
            try:
                await bot.send_message(chat_id=chat_id, text=sanitize.redact_secrets(part),
                                       disable_web_page_preview=True)
            except Exception as exc:  # noqa: BLE001
                logger.error("No se pudo notificar alerta al chat %s: %s", chat_id, exc)
                break


def notify_admins_sync(text: str) -> None:
    """Variante síncrona de `notify_admins` para código que corre en un hilo de
    trabajo (jobs del scheduler, sincronización off-site).

    En esos hilos no hay event-loop vigente y no se puede `await`; se ejecuta
    la corutina con `asyncio.run`. Devuelve cuando el envío terminó (o falló).
    """
    try:
        asyncio.run(notify_admins(text))
    except RuntimeError as exc:
        logger.error("No se pudo ejecutar la alerta por Telegram desde este hilo: %s", exc)


async def notify_admins_document(filename: str, data: bytes, caption: str = "") -> None:
    """Envía un documento (bytes) a todos los admins de Telegram."""
    from core.config import settings
    from services import users as users_srv

    admins = users_srv.list_admin_chat_ids()
    if not admins:
        logger.info("Documento sin destinatarios (no hay admins de Telegram): %s", filename)
        return
    bot = Bot(token=settings().bot_token)
    import io
    for chat_id in admins:
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=io.BytesIO(data),
                filename=filename,
                caption=caption,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("No se pudo enviar documento de alerta al chat %s: %s", chat_id, exc)