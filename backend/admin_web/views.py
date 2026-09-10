"""Renderizado de plantillas y contexto común (usuario actual, CSRF, flashes)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from admin_web import deps

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def render(
    request: Request,
    name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    session_user = deps.current_user(request)
    ctx = {
        "csrf_token": deps.csrf_for(request),
        "current_user": session_user,
        "is_admin": bool(session_user and deps.is_admin(session_user)),
        "ok_msg": request.query_params.get("ok"),
        "err_msg": request.query_params.get("err"),
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(
        request=request, name=name, context=ctx, status_code=status_code
    )