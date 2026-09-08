"""Login/logout de la interfaz web."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from admin_web import deps
from admin_web.views import render
from core import security
from services import audit as audit_srv
from services import web_users as web_users_srv

router = APIRouter(tags=["auth"])


@router.get("/login")
async def login_page(request: Request):
    if deps.current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
async def login_post(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
):
    await deps.check_csrf(request)
    user = web_users_srv.authenticate(username, password)
    if user is None:
        audit_srv.log_action("web_login", "error", web_user_id=None,
                             detalle=f"intento con usuario '{username.strip()}'")
        return render(request, "login.html", {"err_msg": "Usuario o contraseña incorrectos."}, status_code=401)
    token = security.sessions.create(user["username"], user["rol"], user_id=user["id"])
    audit_srv.log_action("web_login", "ok", web_user_id=user["id"])
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=deps.SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=12 * 3600,
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    await deps.check_csrf(request)
    token = request.cookies.get(deps.SESSION_COOKIE)
    if token:
        security.sessions.destroy(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(deps.SESSION_COOKIE)
    return response