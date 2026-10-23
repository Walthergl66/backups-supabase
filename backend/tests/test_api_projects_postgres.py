"""Tests de la API para proyectos PostgreSQL genéricos."""

from fastapi.testclient import TestClient

from services.providers.base import ConnectionTest
from services.web_users import create_web_user


def _login(c):
    admin = c.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPass-12345"},
    ).json()
    return {"Authorization": f"Bearer {admin['access_token']}"}


def test_crear_y_filtrar_proyecto_postgres_por_api(db, monkeypatch):
    from api.app import app
    from services import providers

    monkeypatch.setattr(
        providers.postgres,
        "test_connection",
        lambda connection, timeout=15: ConnectionTest(
            ok=True, detalle="conexión correcta", host="h", database="db",
            server_version="18.6", latency_ms=1.2,
        ),
    )
    create_web_user("admin", "AdminPass-12345", rol="admin")

    with TestClient(app) as c:
        headers = _login(c)

        resp = c.post(
            "/api/projects",
            json={
                "slug": "pg-api",
                "nombre": "Base directa",
                "connection": "postgresql://u:p@h:5432/db",
                "provider": "postgres",
                "schedule": "30 3 * * *",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        listado = c.get("/api/projects?provider=postgres", headers=headers).json()
        assert [p["slug"] for p in listado] == ["pg-api"]
        assert listado[0]["provider"] == "postgres"
        assert listado[0]["backup_options"] == {"no_owner": True, "no_privileges": True}
        assert listado[0]["schedule"] == "30 3 * * *"


def test_test_connection_endpoint(db, monkeypatch):
    from api.app import app
    from services import providers

    monkeypatch.setattr(
        providers.postgres,
        "test_connection",
        lambda connection, timeout=15: ConnectionTest(
            ok=True, detalle="conexión correcta", host="h", database="db",
            server_version="18.6", latency_ms=1.2,
        ),
    )
    create_web_user("admin", "AdminPass-12345", rol="admin")

    with TestClient(app) as c:
        headers = _login(c)

        resp = c.post(
            "/api/projects/test-connection",
            json={"connection": "postgresql://u:p@h:5432/db", "provider": "postgres"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["ok"] is True
        assert data["database"] == "db"
        assert data["server_version"] == "18.6"

        vacio = c.post(
            "/api/projects/test-connection",
            json={"connection": "", "provider": "postgres"},
            headers=headers,
        )
        assert vacio.status_code == 400
