"""API del log de auditoría."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from admin_web.deps import get_current_user
from services import audit as audit_srv

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(limit: int = Query(100), user: dict = Depends(get_current_user)):
    return {"rows": [dict(r) for r in audit_srv.list_audit(limit=min(limit, 500))]}