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
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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


def run_backup(project: dict) -> BackupResult:
    """Ejecuta un pg_dump -Fc de un proyecto dado como dict de services.projects.

    `project` debe incluir: id, slug, connection_plain. Es una operación
    bloqueante; llamarla desde asyncio/túnel del bot con `asyncio.to_thread`.
    """
    start = time.monotonic()
    slug = project["slug"]
    conn_str = project["connection_plain"]
    dest_dir, dest = backup_path_for(slug)

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

    detail = (proc.stderr or "").strip()

    if proc.returncode != 0:
        tail = detail.splitlines()
        tail = "\n".join(tail[-5:]) if tail else "(sin detalle de error)"
        logger.error("Backup '%s' falló (exit %s): %s", slug, proc.returncode, tail)
        return BackupResult(
            ok=False,
            detalle=tail or "pg_dump terminó con error.",
            duracion_seg=elapsed,
            exit_code=proc.returncode,
        )

    if size <= 0:
        msg = "El archivo de backup quedó vacío; se descarta el resultado."
        logger.error("Backup '%s': %s", slug, msg)
        return BackupResult(ok=False, detalle=msg, duracion_seg=elapsed, exit_code=proc.returncode)

    sql_path = _to_sql(dest, slug)
    size_sql = sql_path.stat().st_size if sql_path is not None else 0.0

    removed = _apply_rotation(dest_dir, slug)
    logger.info("Backup '%s' completado en %.1fs (%.1f MB .dump, %.1f MB .sql, %s)",
                slug, elapsed, size / 1e6, size_sql / 1e6, dest)
    return BackupResult(
        ok=True,
        detalle=detail or "Backup completado correctamente.",
        tamaño_archivo=size,
        ruta_archivo=str(dest),
        tamaño_sql=size_sql,
        ruta_sql=str(sql_path) if sql_path is not None else None,
        duracion_seg=elapsed,
        exit_code=proc.returncode,
        archivos_eliminados=removed,
    )


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
        tail = "\n".join((proc.stderr or "").splitlines()[-5:])
        logger.warning("Conversión a SQL '%s' falló (exit %s): %s",
                       dump_path.name, proc.returncode, tail or "(sin detalle)")
        sql_path.unlink(missing_ok=True)
        return None

    logger.info("Convertido '%s' a SQL (%d bytes)", dump_path.name, sql_path.stat().st_size)
    return sql_path


def _apply_rotation(dest_dir: Path, slug: str) -> list[str]:
    """Mantiene solo los últimos N backups por proyecto (configurable).

    Ordena por mtime (los .dump se nombran con marca de tiempo) y borra los
    más antiguos cuando se supera el límite. Cada .dump eliminado arrastra su
    .sql pareja. Solo se invoca tras un éxito.
    """
    keep: int = settings().backup_keep_count
    files = sorted(
        [p for p in dest_dir.glob("*.dump") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    removed: list[str] = []
    if keep < 1:
        keep = 1
    while len(files) > keep:
        oldest = files.pop(0)
        for path in (oldest, oldest.with_suffix(".sql")):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Rotación '%s': no se pudo borrar %s: %s", slug, path.name, exc)
        removed.append(oldest.name)
        logger.info("Rotación '%s': eliminando backup antiguo %s", slug, oldest.name)
    return removed