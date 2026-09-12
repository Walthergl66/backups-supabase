"""Ejecutor de backups en Python puro.

No usa scripts bash ni PowerShell: invoca `pg_dump` directamente vía
subprocess con `shell=False` y rutas gestionadas con `pathlib`, para que
el comportamiento sea idéntico en Linux, macOS y Windows.

Cada backup produce DOS archivos por proyecto:
  - `.dump`: formato custom (-Fc) comprimido, para restauración con
    `pg_restore` o `pg_restore -f out.sql`.
  - `.sql`: texto plano equivalente, generado con `pg_restore --file`
    (conversión local sin conexión a la BD), ideal para inspección o para
    restaurar con `psql`.

Al terminar, ambos se CIFRAN EN DISCO con la clave BACKUP_ENCRYPTION_KEY
(Fernet) y el claro se borra: en `./data/backups` solo existe
`.dump.enc` / `.sql.enc`. Quien quiera enviarlos/restaurarlos debe
descifrarlos con la clave desde `core.crypto`.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core import crypto as crypto_mod
from core import sanitize
from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BackupResult:
    ok: bool
    detalle: str = ""
    tamaño_archivo: float | None = None
    ruta_archivo: str | None = None
    tamaño_sql: float | None = None
    ruta_sql: str | None = None
    duracion_seg: float = 0.0
    exit_code: int | None = None
    archivos_eliminados: list[str] = field(default_factory=list)


def _pg_dump_binary() -> str:
    return "pg_dump"


def _pg_restore_binary() -> str:
    return "pg_restore"


def backup_path_for(slug: str) -> tuple[Path, Path]:
    """Devuelve (directorio del proyecto, ruta del nuevo archivo)."""
    base: Path = settings().backup_dir / slug
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_{stamp}.dump"
    return base, base / filename


def _free_disk_mb(directory: Path) -> int:
    """Espacio libre (MiB) en el filesystem que contiene `directory`."""
    usage = shutil.disk_usage(directory)
    return usage.free // (1024 * 1024)


def _disk_has_enough_space(directory: Path) -> tuple[bool, str]:
    free = _free_disk_mb(directory)
    required = settings().backup_min_free_mb
    if free < required:
        return False, f"Espacio en disco insuficiente: {free} MiB libres, se requieren al menos {required} MiB."
    return True, f"{free} MiB libres (mínimo {required} MiB)."


def run_backup(project: dict) -> BackupResult:
    """Ejecuta un pg_dump -Fc de un proyecto dado como dict de services.projects.

    `project` debe incluir: id, slug, connection_plain. Es una operación
    bloqueante; llamarla desde asyncio/túnel del bot con `asyncio.to_thread`.
    """
    start = time.monotonic()
    slug = project["slug"]
    conn_str = project["connection_plain"]
    dest_dir, dest = backup_path_for(slug)

    ok_space, space_detail = _disk_has_enough_space(dest_dir)
    if not ok_space:
        logger.error("Backup '%s' abortado: %s", slug, space_detail)
        return BackupResult(ok=False, detalle=space_detail, duracion_seg=time.monotonic() - start)

    args = [
        _pg_dump_binary(),
        "--format=custom",   # -Fc
        "--compress=9",
        "--dbname", conn_str,
        "--file", str(dest),
    ]

    logger.info("Iniciando backup del proyecto '%s'...", slug)
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings().backup_timeout_seconds,
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        elapsed = time.monotonic() - start
        msg = "El binario pg_dump no está disponible (instala postgresql-client)."
        logger.error("Backup '%s': %s", slug, msg)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        msg = f"El backup excedió el límite de {settings().backup_timeout_seconds}s y fue cancelado."
        logger.error("Backup '%s': %s", slug, msg)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed)
    except OSError as exc:
        elapsed = time.monotonic() - start
        msg = f"No se pudo lanzar pg_dump: {exc}"
        logger.error("Backup '%s': %s", slug, msg)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed)

    elapsed = time.monotonic() - start
    size = dest.stat().st_size if dest.exists() else 0

    detail = sanitize.redact_secrets((proc.stderr or "").strip())

    if proc.returncode != 0:
        tail = detail.splitlines()
        tail = "\n".join(tail[-5:]) if tail else "(sin detalle de error)"
        # pg_dump puede dejar un archivo parcial en claro: se elimina.
        dest.unlink(missing_ok=True)
        logger.error("Backup '%s' falló (exit %s): %s", slug, proc.returncode, tail)
        return BackupResult(
            ok=False,
            detalle=tail or "pg_dump terminó con error.",
            duracion_seg=elapsed,
            exit_code=proc.returncode,
        )

    if size <= 0:
        msg = "El archivo de backup quedó vacío; se descarta el resultado."
        dest.unlink(missing_ok=True)
        logger.error("Backup '%s': %s", slug, msg)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed, exit_code=proc.returncode)

    verificado, detalle_verif = _verify_dump(dest)
    if not verificado:
        msg = f"El backup no pasó la verificación de restauración: {detalle_verif}"
        logger.error("Backup '%s': %s", slug, msg)
        dest.unlink(missing_ok=True)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed, exit_code=proc.returncode)

    sql_path = _to_sql(dest, slug)
    size_sql = sql_path.stat().st_size if sql_path is not None else 0.0

    try:
        dest_enc = _encrypt_and_remove(dest)
        sql_enc = _encrypt_and_remove(sql_path) if sql_path is not None else None
    except Exception as exc:
        msg = f"No se pudo cifrar el backup en disco: {exc}"
        logger.error("Backup '%s': %s", slug, msg)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed, exit_code=proc.returncode)

    removed = _apply_rotation(dest_dir, slug)
    logger.info("Backup '%s' completado en %.1fs (%.1f MB .dump, %.1f MB .sql, %s)",
                slug, elapsed, size / 1e6, size_sql / 1e6, dest_enc)
    return BackupResult(
        ok=True,
        detalle=detail or "Backup completado correctamente.",
        tamaño_archivo=size,
        ruta_archivo=str(dest_enc),
        tamaño_sql=size_sql,
        ruta_sql=str(sql_enc) if sql_enc is not None else None,
        duracion_seg=elapsed,
        exit_code=proc.returncode,
        archivos_eliminados=removed,
    )


def verify_dump(dump_path: Path) -> tuple[bool, str]:
    """Verifica que el .dump (formato custom -Fc) sea legible y restaurable.

    Usa `pg_restore --list` sobre el archivo en claro (todavía sin cifrar);
    confirma que el catálogo del dump es válido. Si pg_restore no está
    disponible la comprobación se omite (no es un fallo del backup).
    """
    args = [_pg_restore_binary(), "--list", str(dump_path)]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings().backup_timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Verificación de restauración omitida para %s: %s", dump_path.name, exc)
        return True, "verificación omitida (pg_restore no disponible)"

    if proc.returncode != 0:
        tail = sanitize.redact_secrets("\n".join((proc.stderr or "").splitlines()[-5:]))
        return False, tail or "pg_restore --list terminó con error"

    n_entries = len([l for l in proc.stdout.splitlines() if l.strip()])
    logger.info("Dump '%s' verificado: %d entradas legibles por pg_restore", dump_path.name, n_entries)
    return True, f"verificado por pg_restore ({n_entries} entradas)"


def _to_sql(dump_path: Path, slug: str) -> Path | None:
    """Convierte el .dump (formato custom -Fc) a un .sql plano con pg_restore.

    Es local (no necesita conexión a la BD) y falla de forma no fatal: si no
    se puede generar el .sql, el backup se completa igual solo con el .dump.
    """
    sql_path = dump_path.with_suffix(".sql")
    args = [
        _pg_restore_binary(),
        "--format=custom",
        "--file", str(sql_path),
        str(dump_path),
    ]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings().backup_timeout_seconds,
            shell=False,
            check=False,
        )
    except OSError as exc:
        logger.warning("Conversión a SQL '%s' no disponible: %s", dump_path.name, exc)
        sql_path.unlink(missing_ok=True)
        return None

    if proc.returncode != 0 or not sql_path.exists() or sql_path.stat().st_size <= 0:
        tail = sanitize.redact_secrets("\n".join((proc.stderr or "").splitlines()[-5:]))
        logger.warning("Conversión a SQL '%s' falló (exit %s): %s",
                       dump_path.name, proc.returncode, tail or "(sin detalle)")
        sql_path.unlink(missing_ok=True)
        return None

    logger.info("Convertido '%s' a SQL (%d bytes)", dump_path.name, sql_path.stat().st_size)
    return sql_path


def _encrypt_and_remove(plain: Path) -> Path:
    """Cifra un archivo de backup y borra su claro del disco.

    Devuelve la ruta cifrada (`<nombre>.enc`). Si el cifrado falla, el
    archivo en claro se conserva (para no perder el backup) y la excepción
    se propaga; el llamador la convierte en fallo del backup.
    """
    enc = Path(f"{plain}.enc")
    crypto_mod.encrypt_file(plain, enc)
    plain.unlink(missing_ok=True)
    return enc


def _apply_rotation(dest_dir: Path, slug: str) -> list[str]:
    """Mantiene solo los últimos N backups por proyecto (configurable).

    Ordena por mtime (los .dump.enc se nombran con marca de tiempo) y borra
    los más antiguos cuando se supera el límite. Cada .dump.enc eliminado
    arrastra su .sql.enc pareja. Solo se invoca tras un éxito.
    """
    keep: int = settings().backup_keep_count
    files = sorted(
        [p for p in dest_dir.glob("*.dump.enc") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    removed: list[str] = []
    if keep < 1:
        keep = 1
    while len(files) > keep:
        oldest = files.pop(0)
        stem = oldest.name[: -len(".dump.enc")]
        for path in (oldest, oldest.with_name(stem + ".sql.enc")):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Rotación '%s': no se pudo borrar %s: %s", slug, path.name, exc)
        removed.append(oldest.name)
        logger.info("Rotación '%s': eliminando backup antiguo %s", slug, oldest.name)
    return removed