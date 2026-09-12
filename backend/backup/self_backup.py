"""Self-backup de la propia base del panel (SQLite).

La BD del panel guarda cuentas con PAT cifrados, proyectos y auditaría; por
eso también merece respaldo. Usa la API online de `sqlite3.Connection.backup`
(consistente, sin bloquear a la app y respetando WAL), cifra el resultado con
la misma clave BACKUP_ENCRYPTION_KEY y rota las copias antiguas.

No hay un backup automático sin riesgo: durante la copia existe un `.tmp`
temporal en el directorio, que se borra en cuanto se cifra.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from core import crypto as crypto_mod
from core.config import settings

logger = logging.getLogger(__name__)


def run_self_backup() -> Path:
    """Crea una copia cifrada de la BD del panel y devuelve su ruta."""
    src: Path = settings().db_path
    dest_dir: Path = settings().self_backup_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp = dest_dir / f"panel_{stamp}.tmp"
    enc = dest_dir / f"panel_{stamp}.sqlite.enc"

    # Copia online: captura un punto consistente sin detener la app.
    with sqlite3.connect(src) as source:
        with sqlite3.connect(tmp) as target:
            source.backup(target)

    crypto_mod.encrypt_file(tmp, enc)
    tmp.unlink(missing_ok=True)
    _rotate(dest_dir)
    logger.info("Self-backup de la base creado: %s (%d bytes)", enc, enc.stat().st_size if enc.exists() else 0)
    return enc


def _rotate(dest_dir: Path) -> None:
    keep: int = settings().self_backup_keep
    if keep < 1:
        keep = 1
    files = sorted(
        [p for p in dest_dir.glob("panel_*.sqlite.enc") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    while len(files) > keep:
        oldest = files.pop(0)
        try:
            oldest.unlink(missing_ok=True)
            logger.info("Rotación self-backup: eliminando %s", oldest.name)
        except OSError as exc:
            logger.warning("No se pudo borrar self-backup %s: %s", oldest.name, exc)


async def send_latest_to_telegram() -> None:
    """Envía el self-backup más reciente a los admins (descifrado en memoria)."""
    from notify import telegram as notify_mod
    from services import users as users_srv

    dest_dir: Path = settings().self_backup_dir
    files = sorted(
        [p for p in dest_dir.glob("panel_*.sqlite.enc") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    if not files:
        logger.info("No hay self-backups para enviar por Telegram.")
        return
    newest = files[-1]
    try:
        data = crypto_mod.decrypt_file_bytes(newest)
    except Exception as exc:
        logger.error("No se pudo descifrar el self-backup para enviar: %s", exc)
        await notify_mod.notify_admins("⚠️ No se pudo descifrar el self-backup de la base para enviarlo.")
        return

    admins = users_srv.list_admin_chat_ids()
    if not admins:
        logger.info("Self-backup sin destinatarios (no hay admins de Telegram).")
        return

    nombre = newest.name[: -len(".enc")]
    for chat_id in admins:
        await notify_mod.send_document_bytes(
            None, chat_id, nombre, data,
            caption=f"Self-backup de la base del panel ({nombre})",
        )


def maiden_run_safe() -> None:
    """Ejecuta el self-backup una vez al arrancar (si el directorio está vacío)."""
    dest_dir: Path = settings().self_backup_dir
    if not dest_dir.exists() or not any(dest_dir.glob("panel_*.sqlite.enc")):
        run_self_backup()