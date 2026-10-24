"""Comandos básicos: /start, /help y /proyectos."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import _auth_or_deny
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import projects as projects_srv
from services import users as users_srv

_PROVIDER_LABELS = {"supabase": "Supabase", "postgres": "PostgreSQL"}


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return
    has_pat = users_srv.has_pat(chat_id)
    pat_info = (
        ""
        if has_pat
        else "\n/register - registrar tu PAT de Supabase (solo para importar proyectos)"
    )
    text = (
        "Hola {nombre}. Este bot gestiona backups de PostgreSQL: "
        "cualquier base accesible por cadena de conexión y, opcionalmente, "
        "proyectos de Supabase.\n\n"
        "Comandos disponibles:\n"
        "/addbd - agregar una base (Supabase o PostgreSQL directo)\n"
        "{pat_info}"
        "/id - obtener tu chat_id\n"
        "/proyectos - proyectos activos conectados\n"
        "/backup <slug> - respaldo bajo demanda de un proyecto\n"
        "/test <slug> - probar la conexión a la base de datos\n"
        "/status <slug> - estado del proyecto (DB y estado cloud)\n"
        "/historial <slug> - últimos backups del proyecto"
    ).format(nombre=user["nombre"], pat_info=pat_info)
    await notify_mod.send_message(context.bot, chat_id, text)


async def _visible_projects(user: dict) -> list[dict]:
    """Proyectos que el usuario puede ver en /proyectos.

    Los administradores ven todos. El resto ve los de su cuenta de Telegram
    (importados con su PAT) y aquellos sobre los que tiene permisos explícitos.
    """
    projects = projects_srv.list_projects(only_active=True)
    if user["rol"] == "admin":
        return projects

    account = users_srv.find_account_by_chat_id(user["telegram_chat_id"])
    allowed_ids = {
        perm["project_id"] for perm in users_srv.get_permissions(user["id"])
    }
    return [
        p
        for p in projects
        if p["id"] in allowed_ids or (account and p["account_id"] == account["id"])
    ]


async def _cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return

<<<<<<< HEAD
    projects = await _visible_projects(user)
=======
    projects = _visible_projects(user)
>>>>>>> origin/main

    if not projects:
        await notify_mod.send_message(
            context.bot, chat_id, "No hay proyectos activos disponibles para ti."
        )
        return
    lines = [f"Proyectos activos ({len(projects)}):", ""]
    for p in projects:
        ultimo = p.get("ultimo_backup") or "sin backups"
        etiqueta = _PROVIDER_LABELS.get(p.get("provider") or "postgres", "PostgreSQL")
        lines.append(f"• {p['slug']} ({etiqueta}) — último backup: {ultimo}")
    await notify_mod.send_message(context.bot, chat_id, "\n".join(lines))
    audit_srv.log_action("bot_proyectos", "ok", user_id=user["id"])
<<<<<<< HEAD
=======


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
>>>>>>> origin/main
