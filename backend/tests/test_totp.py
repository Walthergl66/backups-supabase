"""Tests del TOTP (segundo factor) de los usuarios web."""

from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core import db
from services import web_users as web_users_srv


@pytest.fixture
def client(db):
    user_id = web_users_srv.create_web_user("admin_totp", "abcdefghijklmno", rol="admin")
    app = create_app()
    with TestClient(app) as c:
        c.app.state.user_id = user_id  # type: ignore[attr-defined]
        yield c, user_id


def _login(client, user_id=None, code=None):
    payload = {"username": "admin_totp", "password": "abcdefghijklmno"}
    if code:
        payload["code"] = code
    return client.post("/api/auth/login", json=payload)


def _secret_for(user_id):
    row = db.fetch_one("SELECT totp_secret FROM web_users WHERE id = ?", (user_id,))
    return row["totp_secret"]


def test_login_sin_2fa_funciona(db):
    web_users_srv.create_web_user("user1", "abcdefghijklmno", rol="viewer")
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/auth/login",
                   json={"username": "user1", "password": "abcdefghijklmno"})
        assert r.status_code == 200
        assert "access_token" in r.json()


def test_totp_disabled_by_default(db):
    web_users_srv.create_web_user("user2", "abcdefghijklmno", rol="viewer")
    assert not web_users_srv.totp_enabled_for(
        db.fetch_one("SELECT id FROM web_users WHERE username='user2'")["id"]
    )


def test_setup_confirm_flow(client, db):
    c, user_id = client
    tok = _login(c).json()["access_token"]
    r = c.post("/api/auth/totp/setup", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["secret"]
    assert "otpauth://totp/" in body["otpauth_url"]
    assert body["qr_svg"].startswith("data:image/svg+xml")

    assert web_users_srv.totp_enabled_for(user_id) is False
    secret = _secret_for(user_id)
    good_code = pyotp.TOTP(secret).now()

    r = c.post("/api/auth/totp/confirm",
               json={"code": "000000"},
               headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400
    assert web_users_srv.totp_enabled_for(user_id) is False

    r = c.post("/api/auth/totp/confirm",
               json={"code": good_code},
               headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert web_users_srv.totp_enabled_for(user_id) is True


def test_login_necesita_code_cuando_totp_activo(client, db):
    c, user_id = client
    tok = _login(c).json()["access_token"]
    c.post("/api/auth/totp/setup", headers={"Authorization": f"Bearer {tok}"})
    good_code = pyotp.TOTP(_secret_for(user_id)).now()
    c.post("/api/auth/totp/confirm", json={"code": good_code},
           headers={"Authorization": f"Bearer {tok}"})

    r = _login(c)
    assert r.status_code == 401
    assert r.json().get("totp_required") is True

    r = _login(c, code="999999")
    assert r.status_code == 401
    assert r.json().get("totp_required") is True

    r = _login(c, code=good_code)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_disable_totp_requiere_code_valido(client, db):
    c, user_id = client
    tok = _login(c).json()["access_token"]
    c.post("/api/auth/totp/setup", headers={"Authorization": f"Bearer {tok}"})
    good_code = pyotp.TOTP(_secret_for(user_id)).now()
    c.post("/api/auth/totp/confirm", json={"code": good_code},
           headers={"Authorization": f"Bearer {tok}"})

    r = c.post("/api/auth/totp/disable", json={"code": "invalido"},
               headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400
    assert web_users_srv.totp_enabled_for(user_id) is True

    r = c.post("/api/auth/totp/disable", json={"code": good_code},
               headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert web_users_srv.totp_enabled_for(user_id) is False

    r = _login(c)
    assert r.status_code == 200


def test_totp_endpoints_requieren_auth(client):
    c, _ = client
    assert c.post("/api/auth/totp/setup").status_code == 401
    assert c.post("/api/auth/totp/confirm", json={"code": "123456"}).status_code == 401
    assert c.post("/api/auth/totp/disable", json={"code": "123456"}).status_code == 401