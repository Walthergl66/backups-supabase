"""Tests de autorización RBAC de la API (admin vs viewer)."""

import pytest

from services.web_users import create_web_user


def _token(headers):
    return {"Authorization": f"Bearer {headers['access_token']}"}


def test_rbac_lecturas_administrativas_solo_admin(db):
    from fastapi.testclient import TestClient
    from api.app import app

    create_web_user("admin", "AdminPass-12345", rol="admin")
    create_web_user("viewer", "ViewerPass-12345", rol="viewer")

    with TestClient(app) as c:
        admin = c.post("/api/auth/login", json={"username": "admin", "password": "AdminPass-12345"}).json()
        viewer = c.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPass-12345"}).json()

        assert c.get("/api/health").status_code == 200

        for path in ("/api/accounts", "/api/users", "/api/web-users"):
            assert c.get(path, headers=_token(admin)).status_code == 200, path
            assert c.get(path, headers=_token(viewer)).status_code == 403, path

        # Lecturas monitoreables permitidas al viewer.
        assert c.get("/api/backups", headers=_token(viewer)).status_code == 200
        assert c.get("/api/projects", headers=_token(viewer)).status_code == 200
        assert c.get("/api/audit", headers=_token(viewer)).status_code == 200

        # Escrituras requieren admin.
        put = c.put(
            "/api/projects/1", json={"nombre": "hack"},
            headers=_token(viewer),
        )
        assert put.status_code in (403,), put.text


def test_rbac_proyectos_eliminados_solo_admin(db):
    from fastapi.testclient import TestClient
    from api.app import app

    create_web_user("admin", "AdminPass-12345", rol="admin")
    create_web_user("viewer", "ViewerPass-12345", rol="viewer")

    with TestClient(app) as c:
        viewer = c.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPass-12345"}).json()
        assert c.get("/api/projects?estado=eliminados", headers=_token(viewer)).status_code == 403


def test_viewer_no_lee_proyecto_archivado_por_id(db):
    """Regresión: un viewer no debe poder leer por id un proyecto desactivado."""
    from fastapi.testclient import TestClient
    from api.app import app
    from services import accounts as accounts_srv
    from services import projects as projects_srv

    create_web_user("admin", "AdminPass-12345", rol="admin")
    create_web_user("viewer", "ViewerPass-12345", rol="viewer")
    acc = accounts_srv.create_account("A", "pat-x")
    pid = projects_srv.create_project(
        "archivado", "Archivado", acc, "postgresql://u:p@h/db", "ref1"
    )
    projects_srv.delete_project(pid)

    with TestClient(app) as c:
        viewer = c.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPass-12345"}).json()
        admin = c.post("/api/auth/login", json={"username": "admin", "password": "AdminPass-12345"}).json()
        assert c.get(f"/api/projects/{pid}", headers=_token(viewer)).status_code == 404
        assert c.get(f"/api/projects/{pid}/history", headers=_token(viewer)).status_code == 404
        assert c.get(f"/api/projects/{pid}", headers=_token(admin)).status_code == 200


def test_sin_token_se_rechaza(db):
    from fastapi.testclient import TestClient
    from api.app import app

    with TestClient(app) as c:
        assert c.get("/api/accounts").status_code == 401