"""Aplicación FastAPI de la interfaz web de administración.

Solo contiene enrutado y presentación; toda la lógica vive en `services/`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from admin_web import deps
from admin_web.routes import accounts, audit, auth, projects, users, web_users
from admin_web.views import render
from services import audit as audit_srv
from services import web_users as web_users_srv


def create_app() -> FastAPI:
    app = FastAPI(title="Supabase Backups Admin", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
        name="static",
    )

    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(projects.router)
    app.include_router(users.router)
    app.include_router(web_users.router)
    app.include_router(audit.router)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        deps.require_user(request)
        ctx = {
            "dashboard": {
                "cuentas": _count("accounts"),
                "proyectos": _count("projects", where="activo = 1"),
                "proyectos_total": _count("projects"),
                "usuarios_telegram": _count("users"),
                "usuarios_web": web_users_srv.count_web_users(),
                "backups_ok": _count("backup_history", where="resultado = 'ok'"),
                "backups_error": _count("backup_history", where="resultado = 'error'"),
                "projects": _active_projects_summary(),
            },
            "recent_audit": audit_srv.list_audit(limit=15),
        }
        return render(request, "dashboard.html", ctx)

    return app


def _count(table: str, where: str | None = None) -> int:
    from core import db
    sql = f"SELECT COUNT(*) AS c FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = db.fetch_one(sql)
    return row["c"] if row else 0


def _active_projects_summary() -> list[dict]:
    from services import projects as projects_srv
    return projects_srv.list_projects(only_active=True)  


app = create_app()