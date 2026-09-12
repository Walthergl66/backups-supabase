"""Punto de entrada: levanta la web (FastAPI) y el bot (Telegram) en un
mismo proceso para simplificar el despliegue con Docker.

¿Por qué un solo proceso en vez de dos servicios? A esta escala un único
contenedor con `restart: unless-stopped` es más fácil de operar, comparte
un solo SQLite sin problemas de acceso entre procesos y consume menos
recursos. Si en el futuro se quisiera escalar, la capa de datos ya está
desacoplada en `services/` para migrar a Postgres y separar los procesos.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from api.app import create_app
from backup import scheduler_jobs
from backup import self_backup as self_backup_mod
from bot import build_application, run_bot_forever
from core import db as db_core
from core import sanitize
from core.config import settings
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import web_users as web_users_srv


def _setup_logging() -> None:
    cfg = settings()
    log_dir = cfg.db_path.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Silencia logs muy ruidosos de librerías de terceros.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)


def bootstrap_admin() -> None:
    """Crea el primer usuario web si todavía no existe ninguno.

    Las credenciales vienen de .env (WEB_ADMIN_USERNAME / WEB_ADMIN_PASSWORD).
    Si el password no está definido, se genera uno aleatorio y se imprime una
    única vez en los logs para que pueda iniciar sesión por primera vez.
    """
    if web_users_srv.count_web_users() > 0:
        return
    cfg = settings()
    password = cfg.web_admin_password or secrets.token_urlsafe(12)
    web_users_srv.create_web_user(
        cfg.web_admin_username or "admin", password, rol="admin"
    )
    audit_srv.log_action(
        "web_bootstrap_admin", "ok",
        detalle=f"se creó el usuario admin inicial '{cfg.web_admin_username or 'admin'}'",
    )
    if not cfg.web_admin_password:
        logging.getLogger(__name__).warning(
            "No había WEB_ADMIN_PASSWORD definido. Se generó una provisional: %s "
            "Inicia sesión y cámbiala cuanto antes.", password
        )
    else:
        logging.getLogger(__name__).info(
            "Usuario admin inicial creado con WEB_ADMIN_PASSWORD del .env."
        )


async def daily_self_backup_job(log: logging.Logger) -> None:
    """Self-backup diario de la base del panel + envío a Telegram (opcional)."""
    try:
        enc = await asyncio.to_thread(self_backup_mod.run_self_backup)
        if enc.exists():
            log.info("Self-backup diario creado: %s (%d bytes)", enc.name, enc.stat().st_size)
        if settings().self_backup_telegram:
            await self_backup_mod.send_latest_to_telegram()
    except Exception as exc:  # noqa: BLE001
        log.exception("Falló el self-backup diario de la base")
        try:
            await notify_mod.notify_admins(
                f"⚠️ Falló el self-backup de la base del panel: {sanitize.redact_secrets(str(exc))}"
            )
        except Exception as notify_exc:  # noqa: BLE001
            log.error("Y además falló la alerta por Telegram: %s", notify_exc)


def setup_scheduler(log: logging.Logger) -> AsyncIOScheduler:
    """Agenda el self-backup diario a la hora y zona configuradas (UTC por defecto)."""
    cfg = settings()
    try:
        tzinfo = ZoneInfo(cfg.self_backup_tz)
    except Exception:  # noqa: BLE001 - zona inválida: se cae a UTC
        tzinfo = ZoneInfo("UTC")

    hour, minute = 3, 0
    try:
        hora, minuto = cfg.self_backup_time.split(":")
        hour, minute = int(hora), int(minuto)
    except Exception:  # noqa: BLE001 - formato inválido: se cae a 03:00
        pass

    scheduler = AsyncIOScheduler(timezone=tzinfo)
    scheduler.add_job(
        daily_self_backup_job,
        CronTrigger(hour=hour, minute=minute, timezone=tzinfo),
        args=[log],
        id="self_backup_daily",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    log.info(
        "Self-backup diario de la base programado a las %02d:%02d (%s)",
        hour, minute, tzinfo,
    )
    return scheduler


async def main() -> None:
    cfg = settings()
    _setup_logging()
    log = logging.getLogger("main")

    db_core.init_db()
    bootstrap_admin()
    self_backup_mod.maiden_run_safe()

    app = create_app()
    bot_app = build_application()
    config = uvicorn.Config(
        app,
        host=cfg.web_host,
        port=cfg.web_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    scheduler = setup_scheduler(log)
    scheduler_jobs.bind(scheduler)
    scheduler_jobs.resync()
    bot_task = asyncio.create_task(run_bot_forever(bot_app))
    log.info("Interfaz web expuesta en http://%s:%s", cfg.web_host, cfg.web_port)
    try:
        await server.serve()
    finally:
        scheduler.shutdown(wait=False)
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass