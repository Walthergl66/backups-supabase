"""Vistas de auditoría y del historial global de backups."""

from __future__ import annotations

from fastapi import APIRouter, Request

from admin_web import deps
from admin_web.views import render
from services import audit as audit_srv

router = APIRouter(tags=["audit"])


@router.get("/audit")
async def audit_view(request: Request):
    deps.require_user(request)
    return render(request, "audit.html", {"rows": audit_srv.list_audit(limit=200)})


@router.get("/backups")
async def backups_view(request: Request):
    deps.require_user(request)
    from core import db
    rows = db.fetch_all(
        """
        SELECT h.*, p.slug
        FROM backup_history h JOIN projects p ON p.id = h.project_id
        ORDER BY h.fecha DESC, h.id DESC
        LIMIT 200
        """
    )
    data = [
        {
            "fecha": r["fecha"],
            "slug": r["slug"],
            "resultado": r["resultado"],
            "tamaño_archivo": r["tamaño_archivo"],
            "ruta_archivo": r["ruta_archivo"],
            "detalle": (r["detalle"] or "")[:200],
        }
        for r in rows
    ]
    return render(request, "backups.html", {"rows": data, "total": len(data)})