"""Historial de backups."""

from __future__ import annotations

from core import db


def record(
    project_id: int,
    resultado: str,
    tamaño_archivo: float | None = None,
    ruta_archivo: str | None = None,
    detalle: str | None = None,
) -> int:
    return db.execute(
        """
        INSERT INTO backup_history (project_id, tamaño_archivo, resultado, ruta_archivo, detalle)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, tamaño_archivo, resultado, ruta_archivo, detalle),
    )


def recent(project_id: int, limit: int = 10) -> list[dict]:
    return [
        {
            "id": r["id"],
            "fecha": r["fecha"],
            "tamaño_archivo": r["tamaño_archivo"],
            "resultado": r["resultado"],
            "ruta_archivo": r["ruta_archivo"],
            "detalle": r["detalle"],
        }
        for r in db.fetch_all(
            """
            SELECT * FROM backup_history
            WHERE project_id = ?
            ORDER BY fecha DESC, id DESC
            LIMIT ?
            """,
            (project_id, limit),
        )
    ]


def last_ok(project_id: int) -> dict | None:
    rows = recent(project_id, limit=1)
    return rows[0] if rows else None