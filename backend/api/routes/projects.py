"""API de proyectos."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_current_user, require_admin
from api.parse import as_bool
from backup import scheduler_jobs
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv
from services import providers

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(
    estado: str = Query("activos"),
    provider: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    # Los proyectos desactivados se gestionan solo desde admin.
    if estado in ("eliminados", "todos") and user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden ver proyectos desactivados.")
    if estado == "eliminados":
        projects = [p for p in projects_srv.list_projects(only_active=False, provider=provider) if not p["activo"]]
    elif estado == "todos":
        projects = projects_srv.list_projects(only_active=False, provider=provider)
    else:
        projects = projects_srv.list_projects(only_active=True, provider=provider)
    return projects


@router.get("/active")
async def active_projects(user: dict = Depends(get_current_user)):
    """Proyectos activos, útil para selects y permisos."""
    return projects_srv.list_projects(only_active=True)


@router.post("/test-connection")
async def test_connection(request: Request, admin: dict = Depends(require_admin)):
    """Prueba una URI de PostgreSQL antes de guardarla."""
    data = await request.json()
    connection = (data.get("connection") or "").strip()
    provider_name = data.get("provider") or "postgres"
    if not connection:
        raise HTTPException(status_code=400, detail="Debes indicar una cadena de conexión.")
    provider = providers.get_provider(provider_name)
    result = await asyncio.to_thread(provider.test_connection, connection)
    return {
        "ok": result.ok,
        "detalle": result.detalle,
        "host": result.host,
        "database": result.database,
        "server_version": result.server_version,
        "latency_ms": result.latency_ms,
    }


@router.post("")
async def create_project(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        account_id = int(data.get("account_id") or 0) or None
    except (TypeError, ValueError):
        account_id = None
    try:
        project_id = projects_srv.create_project(
            slug=data.get("slug", ""),
            nombre=data.get("nombre", ""),
            account_id=account_id,
            connection=data.get("connection", ""),
            project_ref=data.get("project_ref", ""),
            schedule=data.get("schedule") or None,
            provider=data.get("provider") or None,
            backup_options=data.get("backup_options"),
        )
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    scheduler_jobs.resync()
    audit_srv.log_action("web_proyecto_crear", "ok", web_user_id=admin["id"],
                         project_id=project_id, detalle=f"slug '{data.get('slug', '').strip()}'")
    return {"id": project_id}


@router.get("/{project_id}")
async def get_project(project_id: int, user: dict = Depends(get_current_user)):
    project = projects_srv.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    # Los proyectos desactivados solo los ve un admin (coherente con el listado).
    if not project["activo"] and user.get("rol") != "admin":
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return project


@router.put("/{project_id}")
async def update_project(project_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        account_id = int(data.get("account_id") or 0) or None
    except (TypeError, ValueError):
        account_id = None
    try:
        projects_srv.update_project(
            project_id,
            slug=data.get("slug") or None,
            nombre=data.get("nombre") or None,
            account_id=account_id,
            connection=data.get("connection") or None,
            # "" explícito = convertir a PostgreSQL genérica; clave ausente = sin cambio.
            project_ref=data.get("project_ref") if "project_ref" in data else None,
            activo=as_bool(data.get("activo"), None) if "activo" in data else None,
            schedule=data.get("schedule"),
            provider=data.get("provider") or None,
            backup_options=data.get("backup_options") if "backup_options" in data else None,
        )
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    scheduler_jobs.resync()
    audit_srv.log_action("web_proyecto_editar", "ok", web_user_id=admin["id"],
                         project_id=project_id)
    return {"ok": True}


@router.delete("/{project_id}")
async def delete_project(project_id: int, admin: dict = Depends(require_admin)):
    if projects_srv.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    try:
        projects_srv.delete_project(project_id)
    except projects_srv.ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    scheduler_jobs.resync()
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
    scheduler_jobs.resync()
    audit_srv.log_action("web_proyecto_restaurar", "ok", web_user_id=admin["id"],
                         project_id=project_id)
    return {"ok": True}


@router.get("/{project_id}/history")
async def project_history(project_id: int, user: dict = Depends(get_current_user)):
    project = projects_srv.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    if not project["activo"] and user.get("rol") != "admin":
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    stats = projects_srv.project_extra_status(project_id)
    return {
        "project": project,
        "rows": history_srv.recent(project_id, limit=25),
        "stats": stats,
    }