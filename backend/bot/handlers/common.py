"""Helpers compartidos por los comandos del bot de Telegram.

Concentra la validación de autorización, la resolución de proyectos y el
formato de tamaños, para que cada módulo de comandos quede enfocado en su
responsabilidad.
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from notify import telegram as notify_mod
from services import projects as projects_srv
from services import users as users_srv

logger = logging.getLogger(__name__)

UNAUTHORIZED_TEXT = ("No autorizado. Si crees que esto es un error, "
                     "contacta al administrador del sistema.")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _authorized_user(chat_id: int) -> dict | None:
    user = users_srv.authorized_chat(chat_id)
    if user is None:
        logger.info("Chat no registrado intentó usar el bot: chat_id=%s", chat_id)
    return user


async def _auth_or_deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    """Devuelve el usuario autorizado o, si no existe, responde 'no autorizado'."""
    chat_id = update.effective_chat.id
    user = _authorized_user(chat_id)
    if user is None:
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return None
    return user


def _project_for_action(slug: str) -> dict | None:
    project = projects_srv.get_by_slug(slug.strip())
    if project is None or not project["activo"]:
        return None
    return project


def _fmt_size(size: float | None) -> str:
    if size is None:
        return "desconocido"
    if size >= 1e6:
        return f"{size / 1e6:.2f} MB"
    if size >= 1e3:
        return f"{size / 1e3:.1f} KB"
    return f"{size:.0f} B"