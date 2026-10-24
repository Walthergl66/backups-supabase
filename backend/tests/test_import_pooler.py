"""Tests del pooler automático en importación (session mode + inyección de contraseña)."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
import httpx
from services import supabase_api as api


# --- _pick_pooler ---

def test_pick_prefiere_session():
    poolers = [
        {"database_type": "PRIMARY", "pool_mode": "transaction", "connection_string": "t://x"},
        {"database_type": "PRIMARY", "pool_mode": "session", "connection_string": "s://x"},
    ]
    assert api._pick_pooler(poolers, "session").get("connection_string") == "s://x"

def test_pick_fallback_a_transaction():
    poolers = [
        {"database_type": "PRIMARY", "pool_mode": "transaction", "connection_string": "t://x"},
    ]
    assert api._pick_pooler(poolers, "session").get("connection_string") == "t://x"

def test_pick_vacio():
    assert api._pick_pooler([], "session") is None


# --- _inject_password ---

PLACEHOLDER = "postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres"


def test_inyecta_password_placeholder():
    out = api._inject_password(PLACEHOLDER, "s3cret p@ss")
    assert "postgres.xxx:s3cret%20p%40ss@aws" in out
    assert "[YOUR-PASSWORD]" not in out

def test_inyecta_password_sin_placeholder():
    url = "postgresql://postgres.xxx@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    out = api._inject_password(url, "mi_pass")
    assert "mi_pass@aws" in out

def test_none_deja_igual():
    assert api._inject_password(PLACEHOLDER, None) == PLACEHOLDER

def test_password_vacia_deja_igual():
    assert api._inject_password(PLACEHOLDER, "") == PLACEHOLDER

def test_password_especiales():
    out = api._inject_password(PLACEHOLDER, "a&b=c#d")
    assert "a%26b%3Dc%23d@" in out


# --- get_connection_string con mock ---

SESSION_POOLERS = [
    {"database_type": "PRIMARY", "pool_mode": "transaction", "connection_string": "pg://t"},
    {"database_type": "PRIMARY", "pool_mode": "session", "connection_string": "pg://s:[YOUR-PASSWORD]@h:5432/db"},
]

def test_get_cs_session_y_password():
    resp = type("R", (), {"status_code": 200, "json": lambda self: SESSION_POOLERS})()
    with patch.object(api.httpx, "get", return_value=resp):
        out = api.get_connection_string("pat", "ref", mode="session", password="x")
    assert out == "pg://s:x@h:5432/db"

def test_get_cs_sin_password():
    resp = type("R", (), {"status_code": 200, "json": lambda self: SESSION_POOLERS})()
    with patch.object(api.httpx, "get", return_value=resp):
        out = api.get_connection_string("pat", "ref", mode="session", password=None)
    assert "[YOUR-PASSWORD]" in out

def test_get_cs_http_error():
    import httpx
    with patch.object(api.httpx, "get", side_effect=httpx.HTTPError("fail")):
        assert api.get_connection_string("pat", "ref") is None

def test_get_cs_status_500():
    resp = type("R", (), {"status_code": 500, "json": lambda self: []})()
    with patch.object(api.httpx, "get", return_value=resp):
        assert api.get_connection_string("pat", "ref") is None


# --- test_connection ---

def test_test_connection_sin_psql(monkeypatch):
    monkeypatch.setattr(api.shutil, "which", lambda _: None)
    ok, detail = api.test_connection("pg://x:pass@h/db")
    assert ok is True
    assert "omitida" in detail


# --- friendly_db_error ---

@pytest.mark.parametrize("stderr,esperado", [
    ('FATAL: password authentication failed for user "postgres"', "contraseña"),
    ('FATAL: database "postgres" does not exist', "base de datos no coincide"),
    ('FATAL: role "postgres" does not exist', "usuario de la base de datos no existe"),
    ('psql: error: could not translate host name "x" to address', "resolver"),
    ('connection to server at "h" (1.2.3.4), port 5432 failed: Connection timed out', "tardó demasiado"),
    ('connection to server at "h" (1.2.3.4), port 5432 failed: Connection refused', "rechazó"),
    ('FATAL: requires ssl', "SSL"),
    ('otro error raro técnico sit 72k4', "no se pudo conectar"),
])
def test_friendly_db_error(stderr, esperado):
    assert esperado in api.friendly_db_error(stderr) or esperado in api.friendly_db_error(stderr).lower()


# --- SupabaseAPIError / mensajes amigables ---

def test_list_projects_401_mensaje_amigable():
    resp = Mock()
    resp.status_code = 401
    with patch.object(api.httpx, "get", return_value=resp):
        with pytest.raises(api.SupabaseAPIError) as ei:
            api.list_projects("sbp_x")
    assert "token" in str(ei.value).lower()


def test_list_projects_error_red_mensaje_amigable():
    with patch.object(api.httpx, "get", side_effect=httpx.ConnectError("tin")) as m:
        with pytest.raises(api.SupabaseAPIError) as ei:
            api.list_projects("sbp_x")
    assert "conectar" in str(ei.value).lower()
    assert m.called


def test_list_projects_timeout_mensaje_amigable():
    with patch.object(api.httpx, "get", side_effect=httpx.TimeoutException("slow")):
        with pytest.raises(api.SupabaseAPIError) as ei:
            api.list_projects("sbp_x")
    assert "tardó demasiado" in str(ei.value)


def test_list_projects_json_invalido():
    resp = Mock()
    resp.status_code = 200
    resp.json.side_effect = ValueError("bad json")
    with patch.object(api.httpx, "get", return_value=resp):
        with pytest.raises(api.SupabaseAPIError) as ei:
            api.list_projects("sbp_x")
    assert "inesperada" in str(ei.value)


def test_list_projects_ok_parsea():
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = [{"id": "abc", "name": "N", "status": "ACTIVE", "region": "us"}]
    with patch.object(api.httpx, "get", return_value=resp):
        out = api.list_projects("sbp_x")
    assert out == [{"ref": "abc", "name": "N", "status": "ACTIVE", "region": "us"}]


# --- Guard de [YOUR-PASSWORD] en el guardado de proyectos ---

def test_create_project_rechaza_placeholder(db):
    """Regresión: nunca se guarda una cadena con [YOUR-PASSWORD] (los backups
    fallarían con esa palabra como contraseña)."""
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    conn = "postgresql://postgres.aaa:[YOUR-PASSWORD]@aws-0-us.pooler.supabase.com:5432/postgres"
    with pytest.raises(projects_srv.ProjectError, match=r"YOUR-PASSWORD"):
        projects_srv.create_project("mi_prod", "Mi Prod", acc, conn, "ref123")


def test_update_project_rechaza_placeholder(db):
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    pid = projects_srv.create_project(
        "mi_prod", "Mi Prod", acc,
        "postgresql://postgres.aaa:s3cret@aws-0-us.pooler.supabase.com:5432/postgres",
        "ref123",
    )
    assert pid > 0
    with pytest.raises(projects_srv.ProjectError, match=r"YOUR-PASSWORD"):
        projects_srv.update_project(
            pid, connection="postgresql://postgres.aaa:[YOUR-PASSWORD]@h/pg"
        )


# --- C8: parámetros libpq en la connection string ---

def test_connection_rechaza_params_libpq_peligrosos(db):
    """C8: `options=` (y otros) pueden alterar la ejecución; se rechazan."""
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    with pytest.raises(projects_srv.ProjectError, match=r"options"):
        projects_srv.create_project(
            "p1", "P1", acc,
            "postgresql://u:p@h:5432/db?options=-csearch_path%3dtools",
            "ref1",
        )
    with pytest.raises(projects_srv.ProjectError, match=r"host"):
        projects_srv.create_project(
            "p2", "P2", acc,
            "postgresql://u:p@h:5432/db?host=otro-servidor.com",
            "ref2",
        )


def test_connection_permite_params_libpq_seguros(db):
    """sslmode y connect_timeout son inofensivos y habituales: se admiten."""
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    pid = projects_srv.create_project(
        "p3", "P3", acc,
        "postgresql://u:p@h:5432/db?sslmode=require&connect_timeout=10",
        "ref3",
    )
    assert pid > 0


def test_connection_requiere_esquema_y_host(db):
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    with pytest.raises(projects_srv.ProjectError, match=r"postgresql://"):
        projects_srv.create_project("p4", "P4", acc, "mysql://u:p@h/db", "ref4")
    with pytest.raises(projects_srv.ProjectError, match=r"postgresql://"):
        projects_srv.create_project("p5", "P5", acc, "not-a-url", "ref5")
    with pytest.raises(projects_srv.ProjectError, match=r"host"):
        projects_srv.create_project("p6", "P6", acc, "postgresql://", "ref6")


# --- C3: longitud máxima de slug ---

def test_create_project_rechaza_slug_muy_largo(db):
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    largo = "a" * 80
    assert len(largo) > projects_srv.MAX_SLUG_LENGTH
    with pytest.raises(projects_srv.ProjectError, match=r"superar"):
        projects_srv.create_project(
            largo, "Largo", acc, "postgresql://u:p@h/db", "ref1"
        )


def test_update_project_rechaza_slug_muy_largo(db):
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    pid = projects_srv.create_project(
        "ok1", "Ok", acc, "postgresql://u:p@h/db", "ref1"
    )
    with pytest.raises(projects_srv.ProjectError, match=r"superar"):
        projects_srv.update_project(pid, slug="b" * 70)


def test_create_project_acepta_slug_64_caracteres(db):
    from services import projects as projects_srv

    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    ok_slug = "a" * projects_srv.MAX_SLUG_LENGTH
    pid = projects_srv.create_project(
        ok_slug, "Ok", acc, "postgresql://u:p@h/db", "ref1"
    )
    assert pid > 0
