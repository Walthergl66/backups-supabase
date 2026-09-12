"""API de historial de backups."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from core import db

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.get("")
async def list_backups(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    rows = db.fetch_all(
        """
        SELECT bh.*, p.slug
        FROM backup_history bh JOIN projects p ON p.id = bh.project_id
        ORDER BY bh.fecha DESC, bh.id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    total = db.fetch_one("SELECT COUNT(*) AS c FROM backup_history")
    total_count = total["c"] if total else 0
    return {
        "rows": [dict(r) for r in rows],
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "pages": (total_count + page_size - 1) // page_size if total_count else 0,
    }