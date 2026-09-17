"""Tests de refresh tokens persistentes en SQLite (sobreviven al reinicio)."""

import time

import pytest

from services import refresh_tokens
from services import web_users


def _make_user(db, uid=1, username="user1"):
    created = web_users.create_web_user(username, "LargaSegura-2026", rol="admin")
    return {"id": created, "username": username, "rol": "admin"}


def test_create_y_rotacion_en_bd(db):
    store = refresh_tokens.RefreshTokenStore()
    token = store.create(_make_user(db))
    row = db.fetch_one("SELECT token_hash, user_id, rol FROM refresh_sessions")
    assert row is not None
    assert row["rol"] == "admin"
    # No se guarda el token en claro.
    assert row["token_hash"] != token

    rotated = store.validate_and_rotate(token)
    assert rotated is not None
    new_token, entry = rotated
    assert entry["username"] == "user1" and entry["rol"] == "admin"
    # El viejo ya no es válido, el nuevo sí.
    assert store.validate_and_rotate(token) is None
    assert store.validate_and_rotate(new_token) is not None


def test_revoca_y_queda_invalido(db):
    store = refresh_tokens.RefreshTokenStore()
    token = store.create(_make_user(db))
    store.revoke(token)
    assert store.validate_and_rotate(token) is None


def test_reinicio_mantiene_sesiones(db):
    first = refresh_tokens.RefreshTokenStore()
    token = first.create(_make_user(db))
    # Simula un reinicio del proceso: instancia nueva que lee la misma BD.
    second = refresh_tokens.RefreshTokenStore()
    rotated = second.validate_and_rotate(token)
    assert rotated is not None
    assert rotated[1]["username"] == "user1"


def test_podados_vencidos_se_descarta(db):
    store = refresh_tokens.RefreshTokenStore()
    token = store.create(_make_user(db))
    db.execute("UPDATE refresh_sessions SET expires_at = ?", (time.time() - 10,))
    assert store.validate_and_rotate(token) is None
    assert db.fetch_one("SELECT COUNT(*) AS c FROM refresh_sessions")["c"] == 0


def test_purga_semanal_de_sesiones_expirables(db):
    """purge_expired_sessions borra solo las vencidas (job semanal)."""
    store = refresh_tokens.RefreshTokenStore()
    store.create(_make_user(db, username="activa"))
    vencida = _make_user(db, username="vencida")
    db.execute(
        "INSERT INTO refresh_sessions (token_hash, user_id, username, rol, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("deadbeef", vencida["id"], vencida["username"], "admin", time.time(), time.time() - 10),
    )
    assert refresh_tokens.purge_expired_sessions() == 1
    remaining = db.fetch_one("SELECT COUNT(*) AS c FROM refresh_sessions")["c"]
    assert remaining == 1  # solo quedó la activa


def test_refresh_rechazado_si_usuario_desactivado(db):
    from fastapi.testclient import TestClient
    from api.app import app

    uid = web_users.create_web_user("user1", "LargaSegura-2026", rol="viewer")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={
            "username": "user1", "password": "LargaSegura-2026",
        }).status_code == 200
        assert c.post("/api/auth/refresh").status_code == 200

        web_users.update_web_user(uid, activo=False)

        # Desactivado: la sesión deja de renovarse (y se revoca).
        assert c.post("/api/auth/refresh").status_code == 401
        assert c.post("/api/auth/refresh").status_code == 401


def test_refresh_rechazado_si_usuario_eliminado(db):
    from fastapi.testclient import TestClient
    from api.app import app

    uid = web_users.create_web_user("user1", "LargaSegura-2026", rol="viewer")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={
            "username": "user1", "password": "LargaSegura-2026",
        }).status_code == 200

        web_users.delete_web_user(uid)

        assert c.post("/api/auth/refresh").status_code == 401


def test_cookie_secure_segun_esquema(db):
    """La cookie de sesión es Secure solo cuando llega por HTTPS (tras Tailscale)."""
    from fastapi.testclient import TestClient
    from api.app import app
    from services import web_users

    web_users.create_web_user("user1", "LargaSegura-2026", rol="admin")
    body = {"username": "user1", "password": "LargaSegura-2026"}

    with TestClient(app, base_url="http://testserver") as c:
        resp = c.post("/api/auth/login", json=body)
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "Secure" not in set_cookie
        assert "HttpOnly" in set_cookie

    with TestClient(app, base_url="https://testserver") as c:
        resp = c.post("/api/auth/login", json=body)
        assert resp.status_code == 200
        assert "Secure" in resp.headers.get("set-cookie", "")