"""Auth de la API: login JWT y perfil actual."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin_web.deps import current_user
from services import audit as audit_srv
from services import web_users as web_users_srv

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request):
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return JSONResponse(
            {"detail": "Usuario y contraseña son obligatorios."}, status_code=400
        )
    user = web_users_srv.authenticate(username, password)
    if user is None:
        audit_srv.log_action("web_login", "error", web_user_id=None,
                             detalle=f"intento con usuario '{username}'")
        return JSONResponse(
            {"detail": "Usuario o contraseña incorrectos."}, status_code=401
        )
    token = create_token(user)
    audit_srv.log_action("web_login", "ok", web_user_id=user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "username": user["username"], "rol": user["rol"]},
    }


@router.get("/me")
async def me(user: dict) -> dict:
    return {"id": user["id"], "username": user["username"], "rol": user["rol"]}


from core.jwt import create_token  # noqa: E402  (import al final para evitar ciclo)