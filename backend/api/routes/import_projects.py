"""API de importación de proyectos desde Supabase (con usuario de Telegram)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import require_admin
from core import sanitize
from services import accounts as accounts_srv
from services import audit as audit_srv
from services import projects as projects_srv
from services import supabase_api as api_srv
from services import users as users_srv

router = APIRouter(prefix="/api/import", tags=["import_projects"])


@router.post("/fetch")
async def fetch_projects(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    pat = (data.get("pat") or "").strip()
    if not pat:
        raise HTTPException(status_code=400, detail="Debes ingresar un PAT.")

    try:
        projects = await asyncio.to_thread(api_srv.list_projects, pat)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Error al consultar Supabase: {sanitize.redact_secrets(str(exc))}",
        ) from exc

    existing_refs = {p["project_ref"] for p in projects_srv.list_projects(only_active=False)}
    available = [p for p in projects if p["ref"] not in existing_refs]
    return {
        "available": available,
        "existing_count": len(projects) - len(available),
    }


@router.post("/create")
async def create_imported_projects(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    pat = (data.get("pat") or "").strip()
    selected = data.get("selected_projects") or []
    account_name = (data.get("account_name") or "").strip()
    tg_nombre = (data.get("telegram_nombre") or "").strip()
    tg_rol = data.get("telegram_rol") or "usuario"

    try:
        tg_chat = int(data.get("telegram_chat_id") or 0)
    except (TypeError, ValueError):
        tg_chat = 0

    if not pat:
        raise HTTPException(status_code=400, detail="Debes ingresar un PAT.")
    if not selected:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos un proyecto.")
    if not tg_nombre or not tg_chat:
        raise HTTPException(status_code=400,
                            detail="Debes ingresar el nombre y el chat_id del usuario de Telegram.")

    can_backup = bool(data.get("can_backup"))
    can_monitor = bool(data.get("can_monitor"))

    try:
        all_projects = await asyncio.to_thread(api_srv.list_projects, pat)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Error al consultar Supabase: {sanitize.redact_secrets(str(exc))}",
        ) from exc

    account_name = account_name or "Importada desde bot"
    try:
        account_id = accounts_srv.create_account(account_name, pat)
    except accounts_srv.AccountError as exc:
        raise HTTPException(status_code=400, detail=f"Error al crear cuenta: {exc}")

    created = 0
    created_ids: list[int] = []
    errors = []
    for ref in selected:
        project_data = next((p for p in all_projects if p["ref"] == ref), None)
        if not project_data:
            errors.append(f"Proyecto {ref[:8]}... no encontrado")
            continue
        try:
            connection = await asyncio.to_thread(api_srv.get_connection_string, pat, ref)
        except Exception:
            connection = None
        if not connection:
            errors.append(f"{project_data['name']}: no se pudo obtener la connection string")
            continue
        slug = project_data["name"].lower().replace(" ", "-").replace("_", "-")[:30]
        try:
            pid = projects_srv.create_project(
                slug=slug, nombre=project_data["name"], account_id=account_id,
                connection=connection, project_ref=ref,
            )
            created += 1
            created_ids.append(pid)
        except projects_srv.ProjectError as exc:
            errors.append(f"{project_data['name']}: {exc}")

    telegram_user = None
    if created_ids:
        try:
            existing = users_srv.get_user(tg_chat)
            if existing:
                user_id = existing["id"]
                created_user = False
            else:
                user_id = users_srv.create_user(tg_chat, tg_nombre, rol=tg_rol)
                created_user = True

            if tg_rol == "usuario":
                for pid in created_ids:
                    users_srv.upsert_permission(user_id, pid,
                                                can_backup=can_backup, can_monitor=can_monitor)

            slugs = [p["slug"] for p in projects_srv.list_projects(only_active=False)
                     if p["id"] in created_ids]
            telegram_user = {
                "nombre": tg_nombre,
                "telegram_chat_id": tg_chat,
                "rol": tg_rol,
                "created": created_user,
                "projects": slugs or ["(permisos sin asignar)"],
            }
        except users_srv.UserError as exc:
            errors.append(f"Usuario de Telegram: {exc}")

    audit_srv.log_action(
        "web_importar_proyectos", "ok", web_user_id=admin["id"],
        detalle=f"{created} proyectos importados, {len(errors)} errores, chat {tg_chat}",
    )
    return {
        "created": created,
        "errors": errors,
        "account_name": account_name,
        "telegram_user": telegram_user,
    }