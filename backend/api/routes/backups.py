"""API de historial de backups."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from admin_web.deps import get_current_user
from core import db

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.get("")
async def list_backups(limit: int = Query(100), user: dict = Depends(get_current_user)):
    rows = db.fetch_all(
        """
        SELECT bh.*, p.slug
        FROM backup_history bh JOIN projects p ON p.id = bh.project_id
        ORDER BY bh.fecha DESC, bh.id DESC
        LIMIT ?
        """,
        (min(limit, 500),),
    )
    total = db.fetch_one("SELECT COUNT(*) AS c FROM backup_history")
    return {
        "rows": [dict(r) for r in rows],
        "total": total["c"] if total else 0,
    }