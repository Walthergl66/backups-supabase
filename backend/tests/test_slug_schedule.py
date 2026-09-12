"""Tests de slugify, validación de cron y borrado lógico."""

import pytest

from services.projects import (
    ProjectError,
    _validate_schedule,
    create_project,
    delete_project,
    restore_project,
    slugify,
)


def test_slugify_ascii_minusculas_y_guiones():
    assert slugify("Proyecto Múevo") == "proyecto-muevo"
    assert slugify("  Mi   DB  ") == "mi-db"
    assert slugify("Café para dos") == "cafe-para-dos"
    assert slugify("") == ""


def test_create_project_autogenera_slug(db):
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A', 'x')")
    pid = create_project(
        slug="",
        nombre="Mi Dashboard",
        account_id=acc,
        connection="postgresql://u:p@h/d",
        project_ref="ref123",
    )
    row = db.fetch_one("SELECT slug FROM projects WHERE id = ?", (pid,))
    assert row["slug"] == "mi-dashboard"


def test_create_project_con_slug_explicito(db):
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A', 'x')")
    pid = create_project(
        slug="mi-proyecto", nombre="X", account_id=acc,
        connection="postgresql://u:p@h/d", project_ref="ref123",
    )
    assert db.fetch_one("SELECT slug FROM projects WHERE id = ?", (pid,))["slug"] == "mi-proyecto"


def test_slug_invalido_se_rechaza(db):
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A', 'x')")
    with pytest.raises(ProjectError):
        create_project(
            slug="No Válido!", nombre="X", account_id=acc,
            connection="postgresql://u:p@h/d", project_ref="ref123",
        )


def test_schedule_validacion():
    assert _validate_schedule(None) is None
    assert _validate_schedule("") is None
    assert _validate_schedule("30 3 * * *") == "30 3 * * *"
    with pytest.raises(ProjectError):
        _validate_schedule("30 3 * *")  # solo 4 campos
    with pytest.raises(ProjectError):
        _validate_schedule("61 25 * * *")  # valores fuera de rango


def test_delete_project_es_logico_y_restaura(db):
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A', 'x')")
    pid = create_project(
        slug="borrable", nombre="X", account_id=acc,
        connection="postgresql://u:p@h/d", project_ref="ref123",
    )
    delete_project(pid)
    row = db.fetch_one("SELECT slug, activo, archived FROM projects WHERE id = ?", (pid,))
    assert row["activo"] == 0 and row["archived"] == 1
    assert row["slug"].startswith("(eliminado)-")

    restore_project(pid, "borrable-v2")
    row = db.fetch_one("SELECT slug, activo, archived FROM projects WHERE id = ?", (pid,))
    assert row["activo"] == 1 and row["archived"] == 0
    assert row["slug"] == "borrable-v2"