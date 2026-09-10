"""API de proyectos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_current_user, require_admin
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(
    estado: str = Query("activos"),
    user: dict = Depends(get_current_user),
):
    if estado == "eliminados":
        projects = [p for p in projects_srv.list_projects(only_active=False) if not p["activo"]]
    elif estado == "todos":
        projects = projects_srv.list_projects(only_active=False)
    else:
        projects = projects_srv.list_projects(only_active=True)
    return projects


@router.get("/active")
async def active_projects(user: dict = Depends(get_current_user)):
    """Proyectos activos, útil para selects y permisos."""
    return projects_srv.list_projects(only_active=True)


@router.post("")
async def create_project(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        project_id = projects_srv.create_project(
            slug=data.get("slug", ""),
            nombre=data.get("nombre", ""),
            account_id=int(data.get("account_id", 0)),
            connection=data.get("connection", ""),
            project_ref=data.get("project_ref", ""),
        )
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_proyecto_crear", "ok", web_user_id=admin["id"],
                         project_id=project_id, detalle=f"slug '{data.get('slug', '').strip()}'")
    return {"id": project_id}


@router.get("/{project_id}")
async def get_project(project_id: int, user: dict = Depends(get_current_user)):
    project = projects_srv.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return project


@router.put("/{project_id}")
async def update_project(project_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        projects_srv.update_project(
            project_id,
            slug=data.get("slug") or None,
            nombre=data.get("nombre") or None,
            account_id=int(data.get("account_id")) if data.get("account_id") else None,
            connection=data.get("connection") or None,
            project_ref=data.get("project_ref") or None,
            activo=bool(data.get("activo", True)),
        )
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_proyecto_editar", "ok", web_user_id=admin["id"],
                         project_id=project_id)
    return {"ok": True}


@router.delete("/{project_id}")
async def delete_project(project_id: int, admin: dict = Depends(require_admin)):
    try:
        projects_srv.delete_project(project_id)
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_proyecto_eliminar", "ok", web_user_id=admin["id"],
                         project_id=project_id, detalle="eliminación lógica, historial conservado")
    return {"ok": True}


@router.post("/{project_id}/restore")
async def restore_project(project_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    try:
        projects_srv.restore_project(project_id, slug=data.get("slug") or None)
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_proyecto_restaurar", "ok", web_user_id=admin["id"],
                         project_id=project_id)
    return {"ok": True}


@router.get("/{project_id}/history")
async def project_history(project_id: int, user: dict = Depends(get_current_user)):
    project = projects_srv.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    stats = projects_srv.project_extra_status(project_id)
    return {
        "project": project,
        "rows": history_srv.recent(project_id, limit=25),
        "stats": stats,
    }