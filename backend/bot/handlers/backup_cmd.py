"""Comando /backup: respaldo bajo demanda y envío de ambos formatos.

Cada backup genera dos archivos (`.dump` + `.sql`); ambos se envían al chat,
respetando el límite de 50 MB de la Bot API de Telegram.
"""

from __future__ import annotations

import asyncio
import time

from telegram import Update
from telegram.ext import ContextTypes

from backup import offsite as offsite_mod

from backup import runner as backup_runner
from bot.handlers.common import (
    UNAUTHORIZED_TEXT,
    _auth_or_deny,
    _fmt_size,
    _project_for_action,
)
from core.config import settings
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv
from services import users as users_srv

TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024

# Cooldown por chat y lock por proyecto (evita lanzar dos pg_dump sobre el
# mismo proyecto a la vez).
_last_run_at: dict[int, float] = {}
_project_locks: dict[int, asyncio.Lock] = {}


async def _send_document_or_warn(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    project_slug: str,
    ruta: str | None,
    size: float | None,
    label: str,
) -> None:
    """Envía el archivo si entra en el límite de Telegram; si no, avisa."""
    if ruta is None:
        return
    if size is not None and size > TELEGRAM_FILE_LIMIT:
        await notify_mod.send_message(
            context.bot, chat_id,
            f"⚠️ El {label} de {project_slug} ({_fmt_size(size)}) "
            "supera el límite de 50 MB de Telegram; se omite el envío.",
        )
        return
    from pathlib import Path
    from core import crypto as crypto_mod

    try:
        data = crypto_mod.decrypt_file_bytes(Path(ruta))
    except Exception as exc:  # noqa: BLE001
        await notify_mod.send_message(
            context.bot, chat_id,
            f"⚠️ No se pudo descifrar el {label} de {project_slug}: {exc}",
        )
        return
    nombre = Path(ruta).name[: -len(".enc")] if ruta.endswith(".enc") else Path(ruta).name
    await notify_mod.send_document_bytes(
        context.bot, chat_id, nombre, data,
        caption=f"Backup {label} de {project_slug} ({_fmt_size(size)})",
    )


async def _cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await _auth_or_deny(update, context)
    if user is None:
        return

    args = context.args or []
    if not args:
        await notify_mod.send_message(
            context.bot, chat_id, "Uso: /backup <slug> — indica el proyecto a respaldar."
        )
        return

    slug = args[0]
    project = _project_for_action(slug)
    if project is None:
        audit_srv.log_action("bot_backup_intento", "error", user_id=user["id"],
                             detalle=f"slug={slug} no existe o inactivo")
        await notify_mod.send_message(context.bot, chat_id, "Proyecto no encontrado o inactivo.")
        return

    if not users_srv.can(user["id"], project["id"], "can_backup"):
        audit_srv.log_action("bot_backup", "error", user_id=user["id"], project_id=project["id"],
                             detalle="permiso can_backup denegado")
        await notify_mod.send_message(context.bot, chat_id, UNAUTHORIZED_TEXT)
        return

    cooldown = max(0, int(settings().backup_cooldown_seconds))
    if cooldown > 0:
        now = time.monotonic()
        last = _last_run_at.get(chat_id, 0.0)
        remaining = int(cooldown - (now - last))
        if remaining > 0:
            await notify_mod.send_message(
                context.bot, chat_id,
                f"⏳ Todavía está en marcha un backup reciente: espera {remaining}s.",
            )
            return
        _last_run_at[chat_id] = now

    await notify_mod.send_message(
        context.bot, chat_id, f"Iniciando backup de '{project['slug']}'…"
    )
    full_project = projects_srv.get_project(project["id"], include_secret=True)
    lock = _project_locks.setdefault(project["id"], asyncio.Lock())
    async with lock:
        result = await asyncio.to_thread(backup_runner.run_backup, full_project)

    if result.ok:
        size_sql = result.tamaño_sql or 0.0
        sql_note = f"\n• SQL: {_fmt_size(size_sql)}" if result.ruta_sql else "\n• SQL: no disponible"
        detail = (
            f"Backup completado\n"
            f"• Proyecto: {project['slug']}\n"
            f"• Formato .dump: {_fmt_size(result.tamaño_archivo)}"
            f"{sql_note}\n"
            f"• Duración: {result.duracion_seg:.1f}s"
        )
        if result.archivos_eliminados:
            detail += f"\n• Rotación: se eliminaron {len(result.archivos_eliminados)} backup(s) antiguo(s)"
        history_srv.record(
            project["id"], "ok",
            tamaño_archivo=result.tamaño_archivo,
            ruta_archivo=result.ruta_archivo,
            detalle=result.detalle,
        )
        audit_srv.log_action("bot_backup", "ok", user_id=user["id"], project_id=project["id"],
                             detalle=result.detalle)
        await notify_mod.send_message(context.bot, chat_id, detail)
        try:
            await asyncio.to_thread(offsite_mod.sync_new_backups)
        except Exception:  # noqa: BLE001
            pass  # los errores off-site ya avisan; no romper la respuesta del bot
        await _send_document_or_warn(
            context, chat_id, project["slug"],
            result.ruta_sql, result.tamaño_sql, "SQL",
        )
        await _send_document_or_warn(
            context, chat_id, project["slug"],
            result.ruta_archivo, result.tamaño_archivo, ".dump",
        )
    else:
        detail = f"Backup fallido\n• Proyecto: {project['slug']}\n• Motivo: {result.detalle}"
        history_srv.record(project["id"], "error", detalle=result.detalle)
        audit_srv.log_action("bot_backup", "error", user_id=user["id"], project_id=project["id"],
                             detalle=result.detalle)
        await notify_mod.send_message(context.bot, chat_id, detail)