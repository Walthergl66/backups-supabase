"""CRUD de usuarios de Telegram y sus permisos sobre proyectos."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request

from admin_web import deps
from admin_web.views import render
from services import audit as audit_srv
from services import projects as projects_srv
from services import users as users_srv

router = APIRouter(tags=["telegram users"])


def _context_perms(user_id: int) -> dict:
    perms = {p["slug"]: p for p in users_srv.get_permissions(user_id)}
    projects = projects_srv.list_projects(only_active=True)
    return {"user_perms": perms, "projects": projects}


@router.get("/users")
async def list_users(request: Request):
    deps.require_user(request)
    users = []
    for u in users_srv.list_users():
        d = dict(u)
        perms = users_srv.get_permissions(u["id"])
        d["proyectos_puede"] = ", ".join(p["slug"] for p in perms if p["can_backup"] or p["can_monitor"])
        d["es_admin"] = u["rol"] == "admin"
        users.append(d)
    return render(request, "users/list.html", {"telegram_users": users})


@router.get("/users/new")
async def new_user(request: Request):
    deps.require_user(request)
    return render(request, "users/form.html", {"user": None, "projects": projects_srv.list_projects(only_active=True)})


@router.get("/users/{user_id}/edit")
async def edit_user(request: Request, user_id: int):
    deps.require_user(request)
    user = users_srv.get_user_by_id(user_id)
    if user is None:
        return deps.redirect("/users", err="Usuario no encontrado.")
    ctx = {"user": user}
    ctx.update(_context_perms(user_id))
    return render(request, "users/form.html", ctx)


@router.post("/users/create")
async def create_user(
    request: Request,
    telegram_chat_id: int = Form(...),
    nombre: str = Form(""),
    rol: str = Form("usuario"),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        user_id = users_srv.create_user(telegram_chat_id, nombre, rol)
        audit_srv.log_action("web_usuario_crear", "ok", web_user_id=admin["id"],
                             user_id=user_id, detalle=f"chat {telegram_chat_id}")
    except users_srv.UserError as exc:
        return deps.redirect("/users", err=str(exc))
    return deps.redirect("/users", ok="Usuario de Telegram creado.")


@router.post("/users/{user_id}/update")
async def update_user(
    request: Request,
    user_id: int,
    nombre: str = Form(""),
    rol: str = Form("usuario"),
    activo: int = Form(1),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        users_srv.update_user(user_id, nombre=nombre or None, rol=rol, activo=bool(activo))
        audit_srv.log_action("web_usuario_editar", "ok", web_user_id=admin["id"], user_id=user_id)
    except users_srv.UserError as exc:
        return deps.redirect(f"/users/{user_id}/edit", err=str(exc))
    return deps.redirect("/users", ok="Usuario actualizado.")


@router.post("/users/{user_id}/permissions")
async def save_permissions(
    request: Request,
    user_id: int,
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    form = await request.form()
    user = users_srv.get_user_by_id(user_id)
    if user is None:
        return deps.redirect("/users", err="Usuario no encontrado.")
    # Los checkboxes ausentes devuelven "" y los marcados "on".
    for p in projects_srv.list_projects(only_active=True):
        cb = form.get(f"project_{p['id']}")
        cb_m = form.get(f"project_{p['id']}_monitor")
        marked = isinstance(cb, str) and cb.lower() in ("on", "1", "true")
        marked_m = isinstance(cb_m, str) and cb_m.lower() in ("on", "1", "true")
        users_srv.upsert_permission(user_id, p["id"], can_backup=marked, can_monitor=marked_m)
    audit_srv.log_action("web_permisos", "ok", web_user_id=admin["id"], user_id=user_id)
    return deps.redirect("/users", ok="Permisos actualizados.")


@router.post("/users/{user_id}/delete")
async def delete_user(
    request: Request,
    user_id: int,
    confirm: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    if confirm.lower() != "si":
        return deps.redirect("/users", err="Confirma la eliminación escribiendo 'si'.")
    users_srv.delete_user(user_id)
    audit_srv.log_action("web_usuario_eliminar", "ok", web_user_id=admin["id"],
                         user_id=user_id, detalle="id " + str(user_id))
    return deps.redirect("/users", ok="Usuario de Telegram eliminado.")