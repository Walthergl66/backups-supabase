"""Dependencias y helpers de la interfaz web (sesión, autorización, CSRF)."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse

from core import security

SESSION_COOKIE = "sb_session"


def current_session(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    return security.sessions.get(token)


def current_user(request: Request) -> dict | None:
    return current_session(request)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Necesitas el rol admin para realizar esta acción.",
        )
    return user


def is_admin(user: dict) -> bool:
    return user["rol"] == "admin"


def redirect(dest: str, ok: str | None = None, err: str | None = None) -> RedirectResponse:
    url = dest
    params = []
    if ok:
        params.append(f"ok={quote(ok)}")
    if err:
        params.append(f"err={quote(err)}")
    if params:
        url += ("&" if "?" in url else "?") + "&".join(params)
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def quote(value: str) -> str:
    from urllib.parse import quote as _quote
    return _quote(value, safe="")


def csrf_for(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE) or ""
    return security.create_csrf_token(token)


async def check_csrf(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    form = await request.form()
    candidate = form.get("_csrf")
    if not security.verify_csrf(token or "", candidate):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fallo de validación CSRF.")