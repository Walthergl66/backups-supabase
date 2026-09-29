"""Tests de BD PostgreSQL genérica (project_ref vacío = sin Management API)."""

from services.projects import (
    create_project,
    get_project,
    is_supabase_project,
    update_project,
)


def _account(db):
    return db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A', 'x')")


def test_create_project_sin_ref_guarda_generica(db):
    acc = _account(db)
    pid = create_project(
        slug="pg-local", nombre="PG Local", account_id=acc,
        connection="postgresql://u:p@localhost:5432/midb",
    )
    row = db.fetch_one("SELECT project_ref FROM projects WHERE id = ?", (pid,))
    assert row["project_ref"] == ""
    project = get_project(pid)
    assert project["project_ref"] == ""
    assert not is_supabase_project(project)


def test_create_project_con_ref_sigue_supabase(db):
    acc = _account(db)
    pid = create_project(
        slug="sb-app", nombre="Supabase App", account_id=acc,
        connection="postgresql://u:p@h/db", project_ref="abcdefghijklmnopqrst",
    )
    assert is_supabase_project(get_project(pid))


def test_update_project_puede_vaciar_ref(db):
    acc = _account(db)
    pid = create_project(
        slug="mig", nombre="Mig", account_id=acc,
        connection="postgresql://u:p@h/db", project_ref="ref123",
    )
    update_project(pid, project_ref="")
    assert not is_supabase_project(get_project(pid))


def test_update_project_sin_ref_no_cambia(db):
    acc = _account(db)
    pid = create_project(
        slug="keep", nombre="Keep", account_id=acc,
        connection="postgresql://u:p@h/db", project_ref="ref123",
    )
    update_project(pid, nombre="Keep 2")
    assert get_project(pid)["project_ref"] == "ref123"
