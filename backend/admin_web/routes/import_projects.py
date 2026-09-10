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
from services import users as users_srv

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
    telegram_nombre: str = Form(""),
    telegram_chat_id: str = Form(""),
    telegram_rol: str = Form("usuario"),
    tg_can_backup: str | None = Form(None),
    tg_can_monitor: str | None = Form(None),
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

    telegram_nombre = telegram_nombre.strip()
    try:
        chat_id = int(telegram_chat_id or 0)
    except (TypeError, ValueError):
        chat_id = 0

    if not telegram_nombre or not chat_id:
        return render(request, "import_projects.html", {
            "error": "Debes ingresar el nombre y el chat_id del usuario de Telegram.",
            "projects": [],
            "pat": pat,
        })

    can_backup = bool(tg_can_backup)
    can_monitor = bool(tg_can_monitor)

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
    created_ids: list[int] = []
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
            project_id = projects_srv.create_project(
                slug=slug,
                nombre=project_data["name"],
                account_id=account_id,
                connection=connection,
                project_ref=ref,
            )
            created += 1
            created_ids.append(project_id)
        except projects_srv.ProjectError as exc:
            errors.append(f"{project_data['name']}: {exc}")

    # Registro del usuario de Telegram vinculado a los proyectos importados.
    telegram_user = None
    if created_ids:
        try:
            existing = users_srv.get_user(chat_id)
            if existing:
                user_id = existing["id"]
                created_user = False
            else:
                user_id = users_srv.create_user(
                    chat_id,
                    telegram_nombre,
                    rol=telegram_rol,
                )
                created_user = True

            if telegram_rol == "usuario":
                for project_id in created_ids:
                    users_srv.upsert_permission(
                        user_id, project_id,
                        can_backup=can_backup, can_monitor=can_monitor,
                    )

            assigned_slugs = [
                p["slug"]
                for p in projects_srv.list_projects(only_active=False)
                if p["id"] in created_ids
            ]
            telegram_user = {
                "nombre": telegram_nombre,
                "telegram_chat_id": chat_id,
                "rol": telegram_rol,
                "created": created_user,
                "projects": assigned_slugs or ["(permisos sin asignar)"],
            }
        except users_srv.UserError as exc:
            errors.append(f"Usuario de Telegram: {exc}")

    audit_srv.log_action(
        "web_importar_proyectos", "ok", web_user_id=admin["id"],
        detalle=(f"{created} proyectos importados, {len(errors)} errores, "
                 f"chat {chat_id}"),
    )

    return render(request, "import_projects_result.html", {
        "created": created,
        "errors": errors,
        "account_name": account_name,
        "telegram_user": telegram_user,
    })