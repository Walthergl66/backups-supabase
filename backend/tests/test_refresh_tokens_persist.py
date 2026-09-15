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