"""Backups automáticos por proyecto (APScheduler).

Cada proyecto activo con `schedule` (cron de 5 campos) recibe un job que
ejecuta `backup_runner.run_backup` en un hilo y registra el resultado en
`backup_history` + `audit_log`. Si el backup programado falla, se alerta a
los admins por Telegram.

Los jobs se resincronizan con `resync()` (al arrancar y tras cualquier
cambio de proyectos), así nunca quedan huérfanos ni duplicados: primero se
borran los jobs con prefijo `project_` y se vuelven a crear.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.triggers.cron import CronTrigger

from backup import offsite as offsite_mod
from backup import runner as backup_runner
from core import sanitize
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv

logger = logging.getLogger(__name__)

_scheduler = None
_JOB_PREFIX = "project_"


def bind(scheduler) -> None:
    """Registra el scheduler global (llamado desde main())."""
    global _scheduler
    _scheduler = scheduler


def _scheduled_project_ids() -> set[int]:
    jobs = _scheduler.get_jobs() if _scheduler is not None else []
    return {int(job.id.removeprefix(_JOB_PREFIX)) for job in jobs if job.id.startswith(_JOB_PREFIX)}


def resync() -> None:
    """Reconstruye los jobs a partir del estado actual de los proyectos."""
    if _scheduler is None:
        logger.info("Scheduler no disponible aún; jobs programados pendientes de bind().")
        return
    for job in list(_scheduler.get_jobs()):
        if job.id.startswith(_JOB_PREFIX):
            job.remove()

    added = 0
    for project in projects_srv.list_projects(only_active=True):
        expr = (project.get("schedule") or "").strip()
        if not expr:
            continue
        try:
            trigger = CronTrigger.from_crontab(expr)
        except Exception as exc:  # noqa: BLE001 - cron inválido en BD
            logger.warning("Cron inválido '%s' en proyecto '%s': %s", expr, project["slug"], exc)
            continue
        _scheduler.add_job(
            run_scheduled_backup,
            trigger,
            args=[project["id"]],
            id=f"{_JOB_PREFIX}{project['id']}",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=1800,
            max_instances=1,
        )
        added += 1
        logger.info("Proyecto '%s': backup programado con cron '%s'", project["slug"], expr)
    logger.info("Jobs programados sincronizados: %d proyecto(s) con cron.", added)


async def run_scheduled_backup(project_id: int) -> None:
    """Job: ejecuta el backup de un proyecto y registra/avisa el resultado."""
    project = projects_srv.get_project(project_id, include_secret=True)
    if project is None or not project.get("activo"):
        logger.info("Job programado ignorado: proyecto id=%s no está activo.", project_id)
        return

    log = logger.getChild(project["slug"])
    log.info("Backup programado iniciando para '%s'...", project["slug"])
    result = await asyncio.to_thread(backup_runner.run_backup, project)

    if result.ok:
        history_srv.record(
            project_id, "ok",
            tamaño_archivo=result.tamaño_archivo,
            ruta_archivo=result.ruta_archivo,
            detalle=result.detalle,
        )
        audit_srv.log_action("auto_backup", "ok", project_id=project_id,
                             detalle=f"programado: {result.detalle}")
        log.info("Backup programado completado: %s", result.detalle)
        await _sync_offsite()
    else:
        history_srv.record(project_id, "error", detalle=result.detalle)
        audit_srv.log_action("auto_backup", "error", project_id=project_id,
                             detalle=f"programado: {result.detalle}")
        log.error("Backup programado FALLÓ para '%s': %s", project["slug"], result.detalle)
        try:
            await notify_mod.notify_admins(
                "⚠️ Backup programado FALLÓ\n"
                f"• Proyecto: {project['slug']}\n"
                f"• Motivo: {sanitize.redact_secrets(result.detalle)}"
            )
        except Exception as exc:  # noqa: BLE001
            log.error("No se pudo notificar el fallo del backup programado: %s", exc)


async def _sync_offsite() -> None:
    """Copia fuera del sitio (best-effort); los fallos ya avisan por su cuenta."""
    try:
        summary = await asyncio.to_thread(offsite_mod.sync_new_backups)
        if summary["enabled"] and summary["uploaded"]:
            logger.info("Copia off-site: %d subido(s).", summary["uploaded"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("Sincronización off-site falló: %s", exc)