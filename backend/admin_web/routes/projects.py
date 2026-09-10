"""CRUD de proyectos desde la interfaz web."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request

from admin_web import deps
from admin_web.views import render
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import backup_history as history_srv
from services import projects as projects_srv

router = APIRouter(tags=["projects"])


def _accounts_for_form():
    return accounts_srv.list_accounts()


@router.get("/projects")
async def list_projects(request: Request, estado: str = "activos"):
    deps.require_user(request)
    if estado == "eliminados":
        projects = projects_srv.list_projects(only_active=False)
        projects = [p for p in projects if not p["activo"]]
    else:
        projects = projects_srv.list_projects(only_active=True)
    return render(request, "projects/list.html", {"projects": projects, "estado": estado})


@router.get("/projects/new")
async def new_project(request: Request):
    deps.require_user(request)
    return render(request, "projects/form.html", {"project": None, "accounts": _accounts_for_form()})


@router.get("/projects/{project_id}/edit")
async def edit_project(request: Request, project_id: int):
    deps.require_user(request)
    project = projects_srv.get_project(project_id)
    if project is None:
        return deps.redirect("/projects", err="Proyecto no encontrado.")
    return render(request, "projects/form.html",
                  {"project": project, "accounts": _accounts_for_form()})


@router.get("/projects/{project_id}/history")
async def project_history(request: Request, project_id: int):
    deps.require_user(request)
    project = projects_srv.get_project(project_id)
    if project is None:
        return deps.redirect("/projects", err="Proyecto no encontrado.")
    rows = history_srv.recent(project_id, limit=25)
    return render(request, "projects/history.html", {"project": project, "rows": rows})


@router.post("/projects/create")
async def create_project(
    request: Request,
    slug: str = Form(""),
    nombre: str = Form(""),
    account_id: int = Form(...),
    connection: str = Form(""),
    project_ref: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        project_id = projects_srv.create_project(slug, nombre, account_id, connection, project_ref)
        audit_srv.log_action("web_proyecto_crear", "ok", web_user_id=admin["id"],
                             project_id=project_id, detalle=f"slug '{slug.strip()}'")
    except projects_srv.ProjectError as exc:
        return deps.redirect("/projects", err=str(exc))
    return deps.redirect("/projects", ok=f"Proyecto {slug.strip()} creado.")


@router.post("/projects/{project_id}/update")
async def update_project(
    request: Request,
    project_id: int,
    slug: str = Form(""),
    nombre: str = Form(""),
    account_id: int = Form(...),
    connection: str = Form(""),
    project_ref: str = Form(""),
    activo: str | None = Form(None),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        projects_srv.update_project(
            project_id,
            slug=slug or None,
            nombre=nombre or None,
            account_id=account_id,
            connection=connection or None,
            project_ref=project_ref or None,
            activo=bool(activo),
        )
        audit_srv.log_action("web_proyecto_editar", "ok", web_user_id=admin["id"],
                             project_id=project_id)
    except projects_srv.ProjectError as exc:
        return deps.redirect(f"/projects/{project_id}/edit", err=str(exc))
    return deps.redirect("/projects", ok="Proyecto actualizado.")


@router.post("/projects/{project_id}/delete")
async def delete_project(
    request: Request,
    project_id: int,
    confirm: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    if confirm.lower() != "si":
        return deps.redirect("/projects", err="Confirma la eliminación escribiendo 'si'.")
    try:
        projects_srv.delete_project(project_id)
        audit_srv.log_action("web_proyecto_eliminar", "ok", web_user_id=admin["id"],
                             project_id=project_id,
                             detalle="eliminación lógica, historial conservado")
    except projects_srv.ProjectError as exc:
        return deps.redirect("/projects", err=str(exc))
    return deps.redirect("/projects", ok="Proyecto eliminado (historial conservado).")


@router.post("/projects/{project_id}/restore")
async def restore_project(
    request: Request,
    project_id: int,
    slug: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        projects_srv.restore_project(project_id, slug=slug or None)
        audit_srv.log_action("web_proyecto_restaurar", "ok", web_user_id=admin["id"],
                             project_id=project_id)
    except projects_srv.ProjectError as exc:
        return deps.redirect("/projects?estado=eliminados", err=str(exc))
    return deps.redirect("/projects", ok="Proyecto restaurado.")