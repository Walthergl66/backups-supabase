"""Comandos básicos: /start, /help y /proyectos."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import _auth_or_deny
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import projects as projects_srv
from services import users as users_srv


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return
    has_pat = users_srv.has_pat(chat_id)
    pat_info = "\n/register - registrar tu PAT de Supabase" if not has_pat else ""
    addbd_info = "\n/addbd - agregar BD desde tu cuenta de Supabase" if has_pat else ""
    text = (
        "Hola {nombre}. Este bot gestiona backups de Supabase.\n\n"
        "Comandos disponibles:\n"
        "{pat_info}"
        "{addbd_info}"
        "/id - obtener tu chat_id\n"
        "/proyectos - proyectos activos conectados\n"
        "/backup <slug> - respaldo bajo demanda de un proyecto\n"
        "/status <slug> - estado del proyecto (DB y Management API)\n"
        "/historial <slug> - últimos backups del proyecto"
    ).format(nombre=user["nombre"], pat_info=pat_info, addbd_info=addbd_info)
    await notify_mod.send_message(context.bot, chat_id, text)


async def _cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return

    projects = _visible_projects(user)

    if not projects:
        await notify_mod.send_message(
            context.bot, chat_id, "No hay proyectos activos disponibles para ti."
        )
        return
    lines = [f"Proyectos activos ({len(projects)}):", ""]
    for p in projects:
        ultimo = p.get("ultimo_backup") or "sin backups"
        lines.append(f"• {p['slug']} — último backup: {ultimo}")
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))
    audit_srv.log_action("bot_proyectos", "ok", user_id=user["id"])


def _visible_projects(user: dict) -> list[dict]:
    """Proyectos activos que el usuario puede ver.

    Los admins ven todos; el resto solo los que tengan permiso
    `can_backup` o `can_monitor` (nunca el inventario completo).
    """
    projects = projects_srv.list_projects(only_active=True)
    if user["rol"] == "admin":
        return projects
    return [
        p for p in projects
        if users_srv.can(user["id"], p["id"], "can_backup")
        or users_srv.can(user["id"], p["id"], "can_monitor")
    ]