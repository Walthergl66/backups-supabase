"""Tests de contraseñas web, roles y permisos del bot."""

import pytest

from services.users import UserError, can, create_user, upsert_permission
from services.web_users import (
    MIN_PASSWORD_LENGTH,
    WebUserError,
    create_web_user,
    update_web_user,
)


def test_password_minima_al_crear(db):
    with pytest.raises(WebUserError):
        create_web_user("u1", "Corta123", rol="viewer")
    assert create_web_user("u1", "LargaSegura-2026", rol="viewer")
    assert MIN_PASSWORD_LENGTH >= 12


def test_password_minima_al_editar(db):
    uid = create_web_user("u1", "LargaSegura-2026", rol="viewer")
    with pytest.raises(WebUserError):
        update_web_user(uid, password="Corta123")
    update_web_user(uid, password="OtraLargaSegura-77")


def test_role_invalido_rechazado(db):
    with pytest.raises(WebUserError):
        create_web_user("u1", "LargaSegura-2026", rol="admin2")


def test_can_allowlist_bloquea_inyeccion(db):
    uid = create_user(12345, "Bot User")
    with pytest.raises(UserError):
        can(uid, 99, "can_backup; DROP TABLE users; --")
    with pytest.raises(UserError):
        can(uid, 99, "can_whatever")
    assert can(uid, 99, "can_backup") is False


def test_can_admin_implicito(db):
    uid = create_user(11111, "Admin Bot", rol="admin")
    assert can(uid, 99, "can_backup") is True
    assert can(uid, 99, "can_monitor") is True


def test_can_permiso_explicito(db):
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A', 'x')")
    pid = projects_srv.create_project(
        slug="perm", nombre="X", account_id=acc,
        connection="postgresql://u:p@h/d", project_ref="ref123",
    )
    uid = create_user(22222, "Bot User")
    assert can(uid, pid, "can_backup") is False
    upsert_permission(uid, pid, can_backup=True, can_monitor=False)
    assert can(uid, pid, "can_backup") is True
    assert can(uid, pid, "can_monitor") is False