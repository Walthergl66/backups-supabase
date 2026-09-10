"""Aplicación FastAPI de la API REST del panel.

Sirve exclusivamente JSON para el frontend (SPA). Todo lo demás (login de
Telegram, backups, bot) permanece en `services/` y `main.py`.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin_web import deps
from admin_web.routes import accounts, audit, auth, backups, import_projects, projects, users, web_users
from services import audit as audit_srv
from services import projects as projects_srv
from services import web_users as web_users_srv


def create_app() -> FastAPI:
    app = FastAPI(title="Supabase Backups API", docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # se recomienda restringir en producción; ver docker-compose/env
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(projects.router)
    app.include_router(import_projects.router)
    app.include_router(users.router)
    app.include_router(web_users.router)
    app.include_router(backups.router)
    app.include_router(audit.router)

    @app.get("/api/dashboard")
    async def dashboard(user: dict = Depends(deps.get_current_user)):
        return {
            "dashboard": {
                "cuentas": _count("accounts"),
                "proyectos": _count("projects", where="activo = 1"),
                "proyectos_total": _count("projects"),
                "usuarios_telegram": _count("users"),
                "usuarios_web": web_users_srv.count_web_users(),
                "backups_ok": _count("backup_history", where="resultado = 'ok'"),
                "backups_error": _count("backup_history", where="resultado = 'error'"),
                "projects": projects_srv.list_projects(only_active=True),
            },
            "recent_audit": [dict(r) for r in audit_srv.list_audit(limit=15)],
        }

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


def _count(table: str, where: str | None = None) -> int:
    from core import db
    sql = f"SELECT COUNT(*) AS c FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = db.fetch_one(sql)
    return row["c"] if row else 0


app = create_app()