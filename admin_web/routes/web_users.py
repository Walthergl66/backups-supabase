"""CRUD de usuarios de la interfaz web (roles y credenciales)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request

from admin_web import deps
from admin_web.views import render
from services import audit as audit_srv
from services import web_users as web_users_srv

router = APIRouter(tags=["web users"])


@router.get("/web-users")
async def list_web_users(request: Request):
    deps.require_user(request)
    return render(request, "webusers/list.html", {"web_users": web_users_srv.list_web_users()})


@router.get("/web-users/new")
async def new_web_user(request: Request):
    deps.require_admin(request)
    return render(request, "webusers/form.html", {"user": None})


@router.get("/web-users/{user_id}/edit")
async def edit_web_user(request: Request, user_id: int):
    deps.require_admin(request)
    user = web_users_srv.get_web_user_by_id(user_id)
    if user is None:
        return deps.redirect("/web-users", err="Usuario no encontrado.")
    return render(request, "webusers/form.html", {"user": user})


@router.post("/web-users/create")
async def create_web_user(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    rol: str = Form("admin"),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        web_users_srv.create_web_user(username, password, rol)
        audit_srv.log_action("web_usuario_web_crear", "ok", web_user_id=admin["id"],
                             detalle=f"username '{username.strip()}'")
    except web_users_srv.WebUserError as exc:
        return deps.redirect("/web-users", err=str(exc))
    return deps.redirect("/web-users", ok="Usuario web creado.")


@router.post("/web-users/{user_id}/update")
async def update_web_user(
    request: Request,
    user_id: int,
    username: str = Form(""),
    password: str = Form(""),
    rol: str = Form("admin"),
    activo: int = Form(1),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        web_users_srv.update_web_user(
            user_id,
            username=username or None,
            password=password or None,
            rol=rol,
            activo=bool(activo),
        )
        audit_srv.log_action("web_usuario_web_editar", "ok", web_user_id=admin["id"],
                             user_id=user_id)
    except web_users_srv.WebUserError as exc:
        return deps.redirect(f"/web-users/{user_id}/edit", err=str(exc))
    return deps.redirect("/web-users", ok="Usuario web actualizado.")


@router.post("/web-users/{user_id}/delete")
async def delete_web_user(
    request: Request,
    user_id: int,
    confirm: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    if confirm.lower() != "si":
        return deps.redirect("/web-users", err="Confirma la eliminación escribiendo 'si'.")
    if admin["username"] == _username_of(user_id):
        return deps.redirect("/web-users", err="No puedes eliminar tu propio usuario desde esta sesión.")
    try:
        web_users_srv.delete_web_user(user_id)
        audit_srv.log_action("web_usuario_web_eliminar", "ok", web_user_id=admin["id"],
                             user_id=user_id)
    except web_users_srv.WebUserError as exc:
        return deps.redirect("/web-users", err=str(exc))
    return deps.redirect("/web-users", ok="Usuario web eliminado.")


def _username_of(user_id: int) -> str | None:
    u = web_users_srv.get_web_user_by_id(user_id)
    return u["username"] if u else None