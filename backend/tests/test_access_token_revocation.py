"""Tests de revocación de access tokens (jti + blacklist) al logout."""

import pytest


def test_blacklist_revoca_y_detecta():
    from services.access_blacklist import AccessBlacklist

    bl = AccessBlacklist()
    assert bl.is_revoked("abc") is False
    bl.revoke("abc", exp=2_000_000_000)
    assert bl.is_revoked("abc") is True
    # jti sin revocar no se ve afectado.
    assert bl.is_revoked("def") is False
    # None nunca pasa por la lista.
    assert bl.is_revoked(None) is False


def test_blacklist_poda_expirados():
    from services.access_blacklist import AccessBlacklist

    bl = AccessBlacklist()
    import time

    old = int(time.time()) - 10
    bl.revoke("viejo", exp=old)
    assert bl.is_revoked("viejo") is True  # aún en la lista
    bl._last_prune = 0.0  # fuerza la siguiente poda
    assert bl.is_revoked("viejo") is False  # la poda lo descarta al consultar


def test_jwt_lleva_jti(db):
    from core import jwt
    from services import web_users

    uid = web_users.create_web_user("u1", "LargaSegura-2026", rol="admin")
    user = web_users.get_web_user_by_id(uid)
    token = jwt.create_token({"id": user["id"], "username": user["username"], "rol": user["rol"]})
    claims = jwt.decode_token(token)
    assert isinstance(claims.get("jti"), str) and len(claims["jti"]) > 8


def test_token_revocado_queda_invalido_en_deps(db):
    from fastapi.testclient import TestClient
    from api.app import app
    from core import jwt
    from services import access_blacklist, web_users

    web_users.create_web_user("admin", "AdminPass-12345", rol="admin")
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"username": "admin", "password": "AdminPass-12345"}).json()["access_token"]
        claims = jwt.decode_token(tok)
        assert c.get("/api/backups", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
        access_blacklist.blacklist.revoke(claims["jti"], int(claims["exp"]))
        assert c.get("/api/backups", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_logout_revoca_access_token(db):
    from fastapi.testclient import TestClient
    from api.app import app
    from core import jwt
    from services import web_users

    web_users.create_web_user("admin", "AdminPass-12345", rol="admin")
    with TestClient(app) as c:
        resp = c.post("/api/auth/login", json={"username": "admin", "password": "AdminPass-12345"})
        tok = resp.json()["access_token"]
        assert c.post("/api/auth/logout", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
        # El mismo access token ya no sirve tras el logout.
        assert c.get("/api/backups", headers={"Authorization": f"Bearer {tok}"}).status_code == 401