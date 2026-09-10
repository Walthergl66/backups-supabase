"""Comandos /status y /historial: monitoreo de proyectos."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from backup import monitor as monitor_mod
from bot.handlers.common import UNAUTHORIZED_TEXT, _auth_or_deny, _fmt_size, _project_for_action
from notify import telegram as notify_mod
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv
from services import users as users_srv


async def _cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return

    args = context.args or []
    if not args:
        await notify_mod.send_message(
            context.bot, chat_id, "Uso: /status <slug> — indica el proyecto a consultar."
        )
        return

    slug = args[0]
    project = _project_for_action(slug)
    if project is None:
        await notify_mod.send_message(context.bot, chat_id, "Proyecto no encontrado o inactivo.")
        return

    if not users_srv.can(user["id"], project["id"], "can_monitor"):
        audit_srv.log_action("bot_status", "error", user_id=user["id"], project_id=project["id"],
                             detalle="permiso can_monitor denegado")
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    audit_srv.log_action("bot_status", "ok", user_id=user["id"], project_id=project["id"])
    full_project = projects_srv.get_project(project["id"], include_secret=True)
    pat = accounts_srv.get_plaintext_pat(project["account_id"])

    db_ok, db_msg = await asyncio.to_thread(
        monitor_mod.check_database_connection, full_project["connection_plain"]
    )
    api_ok, api_msg = await asyncio.to_thread(
        monitor_mod.check_supabase_api, project["project_ref"], pat
    )
    lines = [
        f"Estado de '{project['slug']}':",
        f"• Conexión DB: {'OK' if db_ok else 'FALLO'}\n  {db_msg}",
        f"• Management API: {'OK' if api_ok else 'FALLO'}\n  {api_msg}",
    ]
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))


async def _cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return

    args = context.args or []
    if not args:
        await notify_mod.send_message(
            context.bot, chat_id, "Uso: /historial <slug> — indica el proyecto a consultar."
        )
        return

    slug = args[0]
    project = _project_for_action(slug)
    if project is None:
        await notify_mod.send_message(context.bot, chat_id, "Proyecto no encontrado o inactivo.")
        return

    if not users_srv.can(user["id"], project["id"], "can_monitor"):
        audit_srv.log_action("bot_historial", "error", user_id=user["id"], project_id=project["id"],
                             detalle="permiso can_monitor denegado")
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    audit_srv.log_action("bot_historial", "ok", user_id=user["id"], project_id=project["id"])
    rows = history_srv.recent(project["id"], limit=10)
    if not rows:
        await notify_mod.send_message(
            context.bot, chat_id, f"Aún no hay backups registrados para '{project['slug']}'."
        )
        return
    lines = [f"Últimos backups de '{project['slug']}':", ""]
    for r in rows:
        estado = "OK" if r["resultado"] == "ok" else "FALLO"
        lines.append(f"• {r['fecha']} — {estado} ({_fmt_size(r['tamaño_archivo'])})")
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))