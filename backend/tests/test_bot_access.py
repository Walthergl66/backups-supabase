"""Tests de acceso del bot de Telegram (autorización y visibilidad)."""

from core import crypto
from services import users as users_srv


def _mk_project(db, slug, account_id=None):
    if account_id is None:
        account_id = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    return db.execute(
        "INSERT INTO projects (slug, nombre, account_id, connection_encrypted, project_ref) "
        "VALUES (?, 'P', ?, ?, 'ref')",
        (slug, account_id, crypto.encrypt("postgresql://u:p@h/d")),
    )


def test_authorized_chat_rechaza_usuario_desactivado(db):
    """Regresión: desactivar a un usuario desde la web lo excluye del bot."""
    uid = users_srv.create_user(12345, "Ana", "usuario")
    assert users_srv.authorized_chat(12345) is not None
    users_srv.update_user(uid, activo=False)
    assert users_srv.authorized_chat(12345) is None
    assert users_srv.authorized_chat(99999) is None


def test_visible_projects_admin_ve_todos(db):
    from bot.handlers.basics import _visible_projects

    admin_id = users_srv.create_user(111, "Admin", "admin")
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    _mk_project(db, "alfa", acc)
    _mk_project(db, "beta", acc)

    admin = users_srv.get_user_by_id(admin_id)
    slugs = {p["slug"] for p in _visible_projects(admin)}
    assert slugs == {"alfa", "beta"}


def test_visible_projects_usuario_sin_permisos_no_enumera(db):
    """Regresión: un usuario sin permisos no ve el inventario de otros."""
    from bot.handlers.basics import _visible_projects

    user_id = users_srv.create_user(222, "Luis", "usuario")
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    _mk_project(db, "alfa", acc)
    _mk_project(db, "beta", acc)

    luis = users_srv.get_user_by_id(user_id)
    assert _visible_projects(luis) == []


def test_visible_projects_usuario_ve_solo_sus_permisos(db):
    from bot.handlers.basics import _visible_projects

    user_id = users_srv.create_user(333, "Luis", "usuario")
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    p1 = _mk_project(db, "alfa", acc)
    _mk_project(db, "beta", acc)
    users_srv.upsert_permission(user_id, p1, can_backup=True, can_monitor=True)

    luis = users_srv.get_user_by_id(user_id)
    slugs = {p["slug"] for p in _visible_projects(luis)}
    assert slugs == {"alfa"}


def test_save_pat_actualiza_cuenta_vinculada(db):
    """Regresión: rotar el PAT con /register debe actualizar también la cuenta
    del bot, que si no conserva el PAT antiguo (revocado) para /status."""
    from services import accounts as accounts_srv

    users_srv.create_user(555, "Ana", "usuario")
    acc = accounts_srv.create_account("Telegram: 555", "pat-viejo")
    users_srv.save_pat(555, "pat-nuevo")
    assert accounts_srv.get_plaintext_pat(acc) == "pat-nuevo"