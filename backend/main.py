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

import uvicorn

from admin_web.app import create_app
from bot import build_application, run_bot_forever
from core import db as db_core
from core.config import settings
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


async def main() -> None:
    cfg = settings()
    _setup_logging()
    log = logging.getLogger("main")

    db_core.init_db()
    bootstrap_admin()

    app = create_app()
    bot_app = build_application()
    config = uvicorn.Config(
        app,
        host=cfg.web_host,
        port=cfg.web_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    bot_task = asyncio.create_task(run_bot_forever(bot_app))
    log.info("Interfaz web expuesta en http://%s:%s", cfg.web_host, cfg.web_port)
    try:
        await server.serve()
    finally:
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