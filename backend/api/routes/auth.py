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


def _qr_svg_data_uri(content: str) -> str:
    """Genera un QR en SVG (sin PIL) y lo codifica como data URI."""
    import io
    import urllib.parse

    import qrcode
    import qrcode.image.svg

    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(content, image_factory=factory, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(buf.getvalue().decode("utf-8"))


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

    # 2FA: si la cuenta tiene TOTP activo, el primer paso solo valida la contraseña.
    code = (data.get("code") or "").strip()
    if user.get("totp_enabled") and not web_users_srv.verify_totp_code(user["id"], code):
        attempts, locked_now = web_users_srv.record_failed_login(username)
        audit_srv.log_action(
            "web_login_2fa", "error", web_user_id=user["id"],
            detalle=f"código 2FA inválido (fallo #{attempts})",
        )
        if locked_now:
            detail = (
                f"Se bloqueó temporalmente la cuenta web '{username}' por "
                f"{web_users_srv.LOCKOUT_MINUTES} min tras "
                f"{web_users_srv.MAX_FAILED_ATTEMPTS} intentos fallidos de 2FA."
            )
            await notify_mod.notify_admins("🚨 " + detail)
        return JSONResponse(
            {"detail": "El código de verificación (2FA) es incorrecto.",
             "totp_required": True},
            status_code=401,
        )

    web_users_srv.reset_failed_logins(username)
    token = create_token(user)
    response = JSONResponse(
        {
            "access_token": token,
            "expires_in": settings().jwt_ttl_seconds,
            "token_type": "bearer",
            "user": {"id": user["id"], "username": user["username"], "rol": user["rol"],
                     "totp_enabled": bool(user.get("totp_enabled"))},
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
    totp = web_users_srv.totp_enabled_for(user["id"])
    return {"id": user["id"], "username": user["username"], "rol": user["rol"],
            "totp_enabled": totp}


@router.post("/refresh")
async def refresh_token(request: Request):
    """Renueva el access token usando el refresh token de la cookie y rota la cookie."""
    raw = request.cookies.get(_REFRESH_COOKIE)
    rotated = refresh_tokens.refresh_store.validate_and_rotate(raw) if raw else None
    if rotated is None:
        return JSONResponse({"detail": "Sesión expirada."}, status_code=401)
    new_refresh, entry = rotated
    raw_user = web_users_srv.get_web_user_by_id(entry["user_id"])
    user = {
        "id": entry["user_id"],
        "username": raw_user["username"] if raw_user else entry["username"],
        "rol": raw_user["rol"] if raw_user else entry["rol"],
        "totp_enabled": bool(raw_user and raw_user.get("totp_enabled")),
    }
    token = create_token(user)
    response = JSONResponse(
        {
            "access_token": token,
            "expires_in": settings().jwt_ttl_seconds,
            "token_type": "bearer",
            "user": {"id": user["id"], "username": user["username"], "rol": user["rol"],
                     "totp_enabled": bool(user.get("totp_enabled"))},
        }
    )
    response.set_cookie(
        _REFRESH_COOKIE, new_refresh, max_age=settings().refresh_ttl_seconds, **_cookie_kwargs(request)
    )
    return response


@router.post("/totp/setup")
async def totp_setup(user: dict = Depends(get_current_user)):
    """Genera un secreto TOTP pendiente para el usuario actual (devuelve QR)."""
    try:
        result = web_users_srv.generate_totp_secret(user["id"])
    except web_users_srv.WebUserError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)
    audit_srv.log_action("totp_setup", "ok", web_user_id=user["id"])
    return {
        "secret": result["secret"],
        "otpauth_url": result["otpauth_url"],
        "qr_svg": _qr_svg_data_uri(result["otpauth_url"]),
    }


@router.post("/totp/confirm")
async def totp_confirm(request: Request, user: dict = Depends(get_current_user)):
    """Confirma el código y activa el 2FA del usuario actual."""
    data = await request.json()
    code = data.get("code") or ""
    try:
        web_users_srv.confirm_totp(user["id"], code)
    except web_users_srv.WebUserError as exc:
        audit_srv.log_action("totp_confirm", "error", web_user_id=user["id"],
                             detalle=str(exc))
        return JSONResponse({"detail": str(exc)}, status_code=400)
    audit_srv.log_action("totp_confirm", "ok", web_user_id=user["id"])
    return {"ok": True}


@router.post("/totp/disable")
async def totp_disable(request: Request, user: dict = Depends(get_current_user)):
    """Desactiva el 2FA del usuario actual (requiere un código válido)."""
    data = await request.json()
    code = data.get("code") or ""
    try:
        web_users_srv.disable_totp(user["id"], code)
    except web_users_srv.WebUserError as exc:
        audit_srv.log_action("totp_disable", "error", web_user_id=user["id"],
                             detalle=str(exc))
        return JSONResponse({"detail": str(exc)}, status_code=400)
    audit_srv.log_action("totp_disable", "ok", web_user_id=user["id"])
    return {"ok": True}


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