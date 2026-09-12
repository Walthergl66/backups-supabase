"""Proyectos de Supabase (cadena de conexión cifrada en reposo)."""

from __future__ import annotations

import re

from apscheduler.triggers.cron import CronTrigger

from core import db, crypto

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ProjectError(Exception):
    pass


def _validate_schedule(schedule: str | None) -> str | None:
    """Valida un cron de 5 campos. Devuelve la expresión normalizada o None."""
    expr = (schedule or "").strip()
    if not expr:
        return None
    if len(expr.split()) != 5:
        raise ProjectError("El cron debe tener 5 campos: minuto hora día mes día-semana (ej. '30 3 * * *').")
    try:
        CronTrigger.from_crontab(expr)
    except Exception as exc:  # noqa: BLE001 - cualquier formato inválido
        raise ProjectError(f"Expresión cron inválida: {exc}") from exc
    return expr


def _dict(row, include_secret: bool = False) -> dict | None:
    if row is None:
        return None
    data = {
        "id": row["id"],
        "slug": row["slug"],
        "nombre": row["nombre"],
        "account_id": row["account_id"],
        "account_nombre": row["account_nombre"] if "account_nombre" in row.keys() else None,
        "project_ref": row["project_ref"],
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
        "schedule": row["schedule"] if "schedule" in row.keys() else None,
        # Rellenado por consultas con JOIN cuando está disponible
        "connection_masked": crypto.mask(crypto.decrypt(row["connection_encrypted"]))
        if not include_secret
        else crypto.decrypt(row["connection_encrypted"]),
        "ultimo_backup": row["ultimo_backup"] if "ultimo_backup" in row.keys() else None,
    }
    if include_secret:
        data["connection_plain"] = crypto.decrypt(row["connection_encrypted"])
    return data


def _base_select(last_backup_join: bool = True) -> str:
    join = (
        """
        LEFT JOIN (
            SELECT project_id, MAX(fecha) AS ultimo_backup
            FROM backup_history
            WHERE resultado = 'ok'
            GROUP BY project_id
        ) bh ON bh.project_id = p.id
        """
        if last_backup_join
        else ""
    )
    return (
        "SELECT p.*, a.nombre AS account_nombre, bh.ultimo_backup "
        f"FROM projects p JOIN accounts a ON a.id = p.account_id {join}"
    )


def create_project(slug: str, nombre: str, account_id: int, connection: str, project_ref: str,
                   schedule: str | None = None) -> int:
    slug = slug.strip()
    nombre = (nombre or "").strip()
    connection = connection.strip()
    project_ref = project_ref.strip()
    schedule = _validate_schedule(schedule)
    if not _SLUG_RE.match(slug):
        raise ProjectError(
            "Slug inválido. Usa solo minúsculas, números, guiones o guiones bajos "
            "(debe empezar por letra o número)."
        )
    if not nombre or not connection or not project_ref:
        raise ProjectError("Nombre, cadena de conexión y project_ref son obligatorios.")
    existing = db.fetch_one("SELECT id FROM projects WHERE slug = ?", (slug,))
    if existing is not None:
        raise ProjectError(f"Ya existe un proyecto con el slug '{slug}'.")
    account = db.fetch_one("SELECT id FROM accounts WHERE id = ?", (account_id,))
    if account is None:
        raise ProjectError("La cuenta asociada no existe.")
    return db.execute(
        """
        INSERT INTO projects (slug, nombre, account_id, connection_encrypted, project_ref, schedule)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (slug, nombre, account_id, crypto.encrypt(connection), project_ref, schedule),
    )


def get_project(project_id: int, include_secret: bool = False) -> dict | None:
    row = db.fetch_one(
        f"{_base_select()} WHERE p.id = ?",
        (project_id,),
    )
    return _dict(row, include_secret=include_secret)


def get_by_slug(slug: str) -> dict | None:
    row = db.fetch_one(
        f"{_base_select()} WHERE p.slug = ?",
        (slug,),
    )
    return _dict(row)


def list_projects(only_active: bool = True) -> list[dict]:
    sql = _base_select()
    if only_active:
        sql += " WHERE p.activo = 1"
    sql += " ORDER BY p.slug"
    return [_dict(r) for r in db.fetch_all(sql)]


def update_project(
    project_id: int,
    slug: str | None = None,
    nombre: str | None = None,
    account_id: int | None = None,
    connection: str | None = None,
    project_ref: str | None = None,
    activo: bool | None = None,
    schedule: str | None = None,
) -> None:
    current = db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if current is None:
        raise ProjectError("El proyecto no existe.")
    new_slug = (slug or "").strip() or current["slug"]
    if new_slug != current["slug"]:
        if not _SLUG_RE.match(new_slug):
            raise ProjectError("Slug inválido.")
        clash = db.fetch_one("SELECT id FROM projects WHERE slug = ? AND id != ?", (new_slug, project_id))
        if clash is not None:
            raise ProjectError(f"Ya existe un proyecto con el slug '{new_slug}'.")
    new_connection = crypto.encrypt(connection.strip()) if connection and connection.strip() else current["connection_encrypted"]
    new_schedule = _validate_schedule(schedule) if schedule is not None else current.get("schedule")
    db.execute(
        """
        UPDATE projects
        SET slug = ?, nombre = ?, account_id = ?, connection_encrypted = ?,
            project_ref = ?, activo = ?, schedule = ?
        WHERE id = ?
        """,
        (
            new_slug,
            (nombre or "").strip() or current["nombre"],
            account_id or current["account_id"],
            new_connection,
            (project_ref or "").strip() or current["project_ref"],
            1 if activo is None else int(activo),
            new_schedule,
            project_id,
        ),
    )


def delete_project(project_id: int) -> None:
    """Eliminación lógica: desactiva el proyecto y libera el slug.

    El historial de backups y el audit_log se conservan intactos.
    """
    current = db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if current is None:
        raise ProjectError("El proyecto no existe.")
    archived_slug = f"(eliminado)-{current['id']}-{current['slug']}"
    db.execute(
        "UPDATE projects SET activo = 0, archived = 1, slug = ? WHERE id = ?",
        (archived_slug, project_id),
    )


def restore_project(project_id: int, slug: str | None = None) -> None:
    """Reactivación desde la vista de proyectos eliminados."""
    current = db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if current is None:
        raise ProjectError("El proyecto no existe.")
    candidate = (slug or "").strip() or current["slug"].split(")-", 1)[-1]
    if not _SLUG_RE.match(candidate):
        raise ProjectError("Slug inválido para restaurar.")
    clash = db.fetch_one("SELECT id FROM projects WHERE slug = ? AND id != ?", (candidate, project_id))
    if clash is not None:
        raise ProjectError(f"El slug '{candidate}' ya está en uso por otro proyecto.")
    db.execute(
        "UPDATE projects SET activo = 1, archived = 0, slug = ? WHERE id = ?",
        (candidate, project_id),
    )


def last_backup_ok(project_id: int) -> str | None:
    row = db.fetch_one(
        "SELECT fecha FROM backup_history WHERE project_id = ? AND resultado = 'ok' ORDER BY fecha DESC LIMIT 1",
        (project_id,),
    )
    return row["fecha"] if row else None


def project_extra_status(project_id: int) -> dict:
    """Datos de estado no sensibles para el panel web."""
    history = db.fetch_all(
        "SELECT resultado, COUNT(*) AS c FROM backup_history WHERE project_id = ? GROUP BY resultado",
        (project_id,),
    )
    stats = {"backups_ok": 0, "backups_error": 0}
    for row in history:
        stats[f"backups_{row['resultado']}"] = row["c"]
    return stats