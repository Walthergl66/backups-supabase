"""Regresión: un proyecto eliminado (archived/activo=0) debe poder reimportarse."""
from __future__ import annotations

from unittest.mock import patch
from fastapi.testclient import TestClient

from services import projects as projects_srv
from services.web_users import create_web_user
from services.accounts import create_account


def _token(headers):
    return {"Authorization": f"Bearer {headers['access_token']}"}


def _fake_refs():
    return [{"ref": "baxqsoqjihtllkakiwxq", "name": "nexo", "status": "ACTIVE_HEALTHY", "region": "us-west-2"}]


def test_proyecto_eliminado_vuelve_a_disponible(db):
    from api.app import app

    create_web_user("admin", "AdminPass-12345", rol="admin")
    with TestClient(app) as c:
        admin = c.post("/api/auth/login", json={"username": "admin", "password": "AdminPass-12345"}).json()
        h = _token(admin)

        # 1) Proyecto ACTIVO en BD → su ref no debe aparecer como disponible
        acc_id = create_account("Cuenta test", "sbp_masked")
        projects_srv.create_project(slug="nexo", nombre="nexo", account_id=acc_id,
                                    connection="postgresql://u:p@h/db", project_ref="baxqsoqjihtllkakiwxq")
        with patch("services.supabase_api.list_projects", return_value=_fake_refs()):
            resp = c.post("/api/import/fetch", json={"pat": "sbp_x"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] == [] and data["existing_count"] == 1

        # 2) Se elimina (lógico: archived=1, activo=0) → libera su ref
        pid = projects_srv.get_by_slug("nexo")["id"]
        projects_srv.delete_project(pid)

        # 3) El ref vuelve a estar disponible para reimportar
        with patch("services.supabase_api.list_projects", return_value=_fake_refs()):
            resp2 = c.post("/api/import/fetch", json={"pat": "sbp_x"}, headers=h)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["existing_count"] == 0
        assert [p["ref"] for p in data2["available"]] == ["baxqsoqjihtllkakiwxq"]