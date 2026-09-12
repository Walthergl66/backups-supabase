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
from core.config import settings
from core import jwt
from core.jwt import create_token
from notify import telegram as notify_mod
from services import access_blacklist
from services import audit as audit_srv
from services import refresh_tokens
from services import web_users as web_users_srv

router = APIRouter(prefix="/api/auth", tags=["auth"])

_REFRESH_COOKIE = "sb_refresh_token"


def _cookie_kwargs(request: Request) -> dict:
    """Cookie HttpOnly/SameSite=Strict, Secure solo sobre HTTPS."""
    return {
        "path": "/api/auth",
        "httponly": True,
        "samesite": "strict",
        "secure": request.url.scheme == "https",
    }


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
    response = JSONResponse(
        {
            "access_token": token,
            "expires_in": settings().jwt_ttl_seconds,
            "token_type": "bearer",
            "user": {"id": user["id"], "username": user["username"], "rol": user["rol"]},
        }
    )
    refresh = refresh_tokens.refresh_store.create(user)
    response.set_cookie(
        _REFRESH_COOKIE, refresh, max_age=settings().refresh_ttl_seconds, **_cookie_kwargs(request)
    )
    audit_srv.log_action("web_login", "ok", web_user_id=user["id"])
    return response


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return {"id": user["id"], "username": user["username"], "rol": user["rol"]}


@router.post("/refresh")
async def refresh_token(request: Request):
    """Renueva el access token usando el refresh token de la cookie y rota la cookie."""
    raw = request.cookies.get(_REFRESH_COOKIE)
    rotated = refresh_tokens.refresh_store.validate_and_rotate(raw) if raw else None
    if rotated is None:
        return JSONResponse({"detail": "Sesión expirada."}, status_code=401)
    new_refresh, entry = rotated
    user = {
        "id": entry["user_id"],
        "username": entry["username"],
        "rol": entry["rol"],
    }
    token = create_token(user)
    response = JSONResponse(
        {
            "access_token": token,
            "expires_in": settings().jwt_ttl_seconds,
            "token_type": "bearer",
            "user": {"id": user["id"], "username": user["username"], "rol": user["rol"]},
        }
    )
    response.set_cookie(
        _REFRESH_COOKIE, new_refresh, max_age=settings().refresh_ttl_seconds, **_cookie_kwargs(request)
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    raw = request.cookies.get(_REFRESH_COOKIE)
    if raw:
        refresh_tokens.refresh_store.revoke(raw)
    # Invalida también el access token presente (si lo hay) en el header.
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        try:
            claims = jwt.decode_token(token.strip())
        except jwt.InvalidToken:
            pass
        else:
            if claims.get("jti"):
                access_blacklist.blacklist.revoke(claims["jti"], int(claims.get("exp", 0)))
    response = JSONResponse({"ok": True})
    response.delete_cookie(_REFRESH_COOKIE, path="/api/auth")
    return response