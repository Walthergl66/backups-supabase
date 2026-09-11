"""Aplicación FastAPI de la API REST del panel.

Sirve exclusivamente JSON para el frontend (SPA). Todo lo demás (login de
Telegram, backups, bot) permanece en `services/` y `main.py`.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from api import deps
from api.rate_limit import _client_address, limiter, should_notify_rate_limit
from api.routes import accounts, audit, auth, backups, import_projects, projects, users, web_users
from core.config import settings
from notify import telegram as notify_mod
from services import audit as audit_srv
from services import projects as projects_srv
from services import web_users as web_users_srv

# Las docs se sirven bajo /api/* para que el proxy de nginx (location /api/)
# las reenvíe al backend en vez de a la SPA.
DOCS_URL = "/api/docs"
REDOC_URL = "/api/redoc"
OPENAPI_URL = "/api/openapi.json"


def create_app() -> FastAPI:
    docs_enabled = settings().web_docs_enabled
    app = FastAPI(
        title="Supabase Backups API",
        description="API REST del panel de backups de Supabase.\n\n"
                    "Autentícate con el botón **Authorize**: pega SOLO el token JWT "
                    "(login en `POST /api/auth/login`); la API lo envía como `Bearer`.",
        version="1.0.0",
        docs_url=DOCS_URL if docs_enabled else None,
        redoc_url=REDOC_URL if docs_enabled else None,
        openapi_url=OPENAPI_URL if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings().cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter

    async def _rate_limit_handler(request, exc: RateLimitExceeded):
        if should_notify_rate_limit():
            ip = _client_address(request)
            await notify_mod.notify_admins(
                f"🚨 Posible ataque de fuerza bruta al panel: se superó el límite "
                f"de intentos de login (HTTP 429) desde la IP {ip}."
            )
        return JSONResponse(
            {"detail": "Demasiados intentos. Espera un momento e inténtalo de nuevo."},
            status_code=429,
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # Esquema de seguridad Bearer para el botón "Authorize" de Swagger.
    # Solo afecta a la documentación: la autenticación real la leen las deps.
    if docs_enabled:
        _setup_bearer_auth(app)

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


def _setup_bearer_auth(app: FastAPI) -> None:
    """Añade el esquema HTTP Bearer al OpenAPI para el botón Authorize.

    No cambia la autorización en runtime (la manejan las dependencias de
    `api/deps.py` leyendo el header `Authorization`), solo enriquece la
    documentación de Swagger/ReDoc.
    """
    def _openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = FastAPI.openapi(app)
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        schema["security"] = [{"bearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = _openapi  # type: ignore[method-assign]


def _count(table: str, where: str | None = None) -> int:
    from core import db
    sql = f"SELECT COUNT(*) AS c FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = db.fetch_one(sql)
    return row["c"] if row else 0


app = create_app()