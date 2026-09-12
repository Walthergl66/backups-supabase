"""Log de auditoría transversal (bot y web)."""

from __future__ import annotations

from datetime import datetime, timedelta

from core import db


def log_action(
    accion: str,
    resultado: str,
    user_id: int | None = None,
    web_user_id: int | None = None,
    project_id: int | None = None,
    detalle: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO audit_log (user_id, web_user_id, project_id, accion, resultado, detalle)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, web_user_id, project_id, accion, resultado, detalle),
    )


def list_audit(limit: int = 100, offset: int = 0) -> list:
    return db.fetch_all(
        """
        SELECT a.*,
               u.nombre   AS telegram_user,
               w.username AS web_user,
               p.slug     AS project_slug
        FROM audit_log a
        LEFT JOIN users      u ON u.id = a.user_id
        LEFT JOIN web_users  w ON w.id = a.web_user_id
        LEFT JOIN projects   p ON p.id = a.project_id
        ORDER BY a.timestamp DESC, a.id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )


def count_audit() -> int:
    row = db.fetch_one("SELECT COUNT(*) AS c FROM audit_log")
    return row["c"] if row else 0


def purge_old(days: int) -> int:
    """Borra entradas de auditoría anteriores a `days` días. Devuelve nº borrado."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))
        return cur.rowcount