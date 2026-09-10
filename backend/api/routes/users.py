"""API de usuarios de Telegram y sus permisos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user, require_admin
from services import audit as audit_srv
from services import users as users_srv

router = APIRouter(prefix="/api/users", tags=["telegram users"])


def _user_with_perms(u: dict) -> dict:
    d = dict(u)
    perms = users_srv.get_permissions(u["id"])
    d["proyectos_puede"] = ", ".join(p["slug"] for p in perms if p["can_backup"] or p["can_monitor"])
    d["es_admin"] = u["rol"] == "admin"
    return d


@router.get("")
async def list_users(user: dict = Depends(get_current_user)):
    return [_user_with_perms(u) for u in users_srv.list_users()]


@router.post("")
async def create_user(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        user_id = users_srv.create_user(
            int(data.get("telegram_chat_id", 0)),
            data.get("nombre", ""),
            rol=data.get("rol", "usuario"),
        )
    except users_srv.UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_usuario_crear", "ok", web_user_id=admin["id"],
                         user_id=user_id, detalle=f"chat {data.get('telegram_chat_id')}")
    return {"id": user_id}


@router.get("/{user_id}")
async def get_user(user_id: int, user: dict = Depends(get_current_user)):
    u = users_srv.get_user_by_id(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return {
        **u,
        "permissions": users_srv.get_permissions(user_id),
    }


@router.put("/{user_id}")
async def update_user(user_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        users_srv.update_user(
            user_id,
            nombre=data.get("nombre") or None,
            rol=data.get("rol") or None,
            activo=bool(data.get("activo", True)),
        )
    except users_srv.UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_usuario_editar", "ok", web_user_id=admin["id"], user_id=user_id)
    return {"ok": True}


@router.post("/{user_id}/permissions")
async def save_permissions(user_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    u = users_srv.get_user_by_id(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    # payload: {"permissions": [{"project_id":1,"can_backup":true,"can_monitor":false}, ...]}
    for perm in data.get("permissions", []):
        users_srv.upsert_permission(
            user_id,
            int(perm["project_id"]),
            can_backup=bool(perm.get("can_backup", False)),
            can_monitor=bool(perm.get("can_monitor", False)),
        )
    audit_srv.log_action("web_permisos", "ok", web_user_id=admin["id"], user_id=user_id)
    return {"ok": True}


@router.delete("/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    users_srv.delete_user(user_id)
    audit_srv.log_action("web_usuario_eliminar", "ok", web_user_id=admin["id"],
                         user_id=user_id, detalle="id " + str(user_id))
    return {"ok": True}