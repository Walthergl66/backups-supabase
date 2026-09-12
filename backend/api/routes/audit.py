"""API del log de auditoría."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from services import audit as audit_srv

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    rows = audit_srv.list_audit(limit=page_size, offset=offset)
    total = audit_srv.count_audit()
    return {
        "rows": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }