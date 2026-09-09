"""Importar proyectos desde Supabase de forma automatizada."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Form, Request

from admin_web import deps
from admin_web.views import render
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import projects as projects_srv
from services import supabase_api as api_srv

router = APIRouter(tags=["import_projects"])


@router.get("/import-projects")
async def import_projects_form(request: Request):
    deps.require_admin(request)
    return render(request, "import_projects.html", {"projects": [], "pat": ""})


@router.post("/import-projects/fetch")
async def fetch_projects(
    request: Request,
    pat: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)

    if not pat.strip():
        return render(request, "import_projects.html", {
            "error": "Debes ingresar un PAT.",
            "projects": [],
            "pat": pat,
        })

    try:
        projects = await asyncio.to_thread(api_srv.list_projects, pat.strip())
    except Exception as exc:
        return render(request, "import_projects.html", {
            "error": f"Error al consultar Supabase: {exc}",
            "projects": [],
            "pat": pat,
        })

    if not projects:
        return render(request, "import_projects.html", {
            "info": "No se encontraron proyectos en esta cuenta.",
            "projects": [],
            "pat": pat,
        })

    existing_refs = set()
    for p in projects_srv.list_projects(only_active=False):
        existing_refs.add(p["project_ref"])

    available = [p for p in projects if p["ref"] not in existing_refs]

    return render(request, "import_projects.html", {
        "projects": available,
        "existing_count": len(projects) - len(available),
        "pat": pat,
    })


@router.post("/import-projects/create")
async def create_imported_projects(
    request: Request,
    pat: str = Form(""),
    account_name: str = Form(""),
    selected_projects: list[str] = Form([]),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)

    if not pat.strip():
        return render(request, "import_projects.html", {
            "error": "Debes ingresar un PAT.",
            "projects": [],
            "pat": pat,
        })

    if not selected_projects:
        return render(request, "import_projects.html", {
            "error": "Debes seleccionar al menos un proyecto.",
            "projects": [],
            "pat": pat,
        })

    try:
        all_projects = await asyncio.to_thread(api_srv.list_projects, pat.strip())
    except Exception as exc:
        return render(request, "import_projects.html", {
            "error": f"Error al consultar Supabase: {exc}",
            "projects": [],
            "pat": pat,
        })

    account_name = account_name.strip() or "Importada desde bot"
    try:
        account_id = accounts_srv.create_account(account_name, pat.strip())
    except accounts_srv.AccountError as exc:
        return render(request, "import_projects.html", {
            "error": f"Error al crear cuenta: {exc}",
            "projects": [],
            "pat": pat,
        })

    created = 0
    errors = []
    for ref in selected_projects:
        project_data = next((p for p in all_projects if p["ref"] == ref), None)
        if not project_data:
            errors.append(f"Proyecto {ref[:8]}... no encontrado")
            continue

        try:
            connection = await asyncio.to_thread(api_srv.get_connection_string, pat.strip(), ref)
        except Exception:
            connection = None

        if not connection:
            errors.append(f"{project_data['name']}: no se pudo obtener la connection string")
            continue

        slug = project_data["name"].lower().replace(" ", "-").replace("_", "-")
        slug = slug[:30]

        try:
            projects_srv.create_project(
                slug=slug,
                nombre=project_data["name"],
                account_id=account_id,
                connection=connection,
                project_ref=ref,
            )
            created += 1
        except projects_srv.ProjectError as exc:
            errors.append(f"{project_data['name']}: {exc}")

    audit_srv.log_action("web_importar_proyectos", "ok", web_user_id=admin["id"],
                         detalle=f"{created} proyectos importados, {len(errors)} errores")

    return render(request, "import_projects_result.html", {
        "created": created,
        "errors": errors,
        "account_name": account_name,
    })
