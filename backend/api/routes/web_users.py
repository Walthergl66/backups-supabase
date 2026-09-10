"""API de usuarios de la interfaz web (admin | viewer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user, require_admin
from services import audit as audit_srv
from services import web_users as web_users_srv

router = APIRouter(prefix="/api/web-users", tags=["web users"])


@router.get("")
async def list_web_users(user: dict = Depends(get_current_user)):
    return web_users_srv.list_web_users()


@router.post("")
async def create_web_user(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        user_id = web_users_srv.create_web_user(
            data.get("username", ""),
            data.get("password", ""),
            rol=data.get("rol", "admin"),
        )
    except web_users_srv.WebUserError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_usuario_web_crear", "ok", web_user_id=admin["id"],
                         detalle=f"usuario '{data.get('username', '').strip()}'")
    return {"id": user_id}


@router.get("/{user_id}")
async def get_web_user(user_id: int, user: dict = Depends(get_current_user)):
    u = web_users_srv.get_web_user_by_id(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario web no encontrado.")
    return u


@router.put("/{user_id}")
async def update_web_user(user_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        web_users_srv.update_web_user(
            user_id,
            username=data.get("username") or None,
            password=data.get("password") or None,
            rol=data.get("rol") or None,
            activo=bool(data.get("activo", True)),
        )
    except web_users_srv.WebUserError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_usuario_web_editar", "ok", web_user_id=admin["id"], user_id=user_id)
    return {"ok": True}


@router.delete("/{user_id}")
async def delete_web_user(user_id: int, admin: dict = Depends(require_admin)):
    try:
        web_users_srv.delete_web_user(user_id)
    except web_users_srv.WebUserError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_usuario_web_eliminar", "ok", web_user_id=admin["id"],
                         user_id=user_id, detalle="id " + str(user_id))
    return {"ok": True}