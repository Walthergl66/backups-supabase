"""Auth de la API: login JWT y perfil actual.

Protección anti fuerza bruta (en capas):
  1. Rate-limit por IP real (`slowapi`) sobre POST /api/auth/login.
  2. Lockout persistente por usuario en la BD tras intentos fallidos.
  3. Alerta por Telegram a los admins cuando una cuenta queda bloqueada.
"""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.deps import get_current_user
from api.rate_limit import limiter
from core.jwt import create_token
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import web_users as web_users_srv

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
@limiter.limit("5/minute")
@limiter.limit("60/hour")
async def login(request: Request):
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return JSONResponse(
            {"detail": "Usuario y contraseña son obligatorios."}, status_code=400
        )

    locked_for = web_users_srv.get_lock_seconds(username)
    if locked_for > 0:
        audit_srv.log_action(
            "web_login", "error", web_user_id=None,
            detalle=f"bloqueado temporalmente el usuario '{username}'",
        )
        return JSONResponse(
            {"detail": f"Cuenta bloqueada temporalmente. Intenta de nuevo en "
                       f"{ceil(locked_for / 60)} min."},
            status_code=423,
        )

    user = web_users_srv.authenticate(username, password)
    if user is None:
        attempts, locked_now = web_users_srv.record_failed_login(username)
        audit_srv.log_action(
            "web_login", "error", web_user_id=None,
            detalle=f"intento con usuario '{username}' (fallo #{attempts})",
        )
        if locked_now:
            detail = (
                f"Se bloqueó temporalmente la cuenta web '{username}' por "
                f"{web_users_srv.LOCKOUT_MINUTES} min tras "
                f"{web_users_srv.MAX_FAILED_ATTEMPTS} intentos fallidos."
            )
            await notify_mod.notify_admins("🚨 " + detail)
        return JSONResponse(
            {"detail": "Usuario o contraseña incorrectos."}, status_code=401
        )
    web_users_srv.reset_failed_logins(username)
    token = create_token(user)
    audit_srv.log_action("web_login", "ok", web_user_id=user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "username": user["username"], "rol": user["rol"]},
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return {"id": user["id"], "username": user["username"], "rol": user["rol"]}