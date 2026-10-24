"""Tests del modelo PostgreSQL genérico (proyectos y grupos de conexión)."""

import json

import pytest

from services import accounts as accounts_srv
from services.projects import (
    ProjectError,
    create_project,
    get_by_slug,
    list_projects,
    update_project,
)

PG_DSN = "postgresql://usuario:clave@db.example.com:5432/mibase"


def test_proyecto_generico_usa_el_grupo_por_defecto(db):
    pid = create_project(
        slug="pg-generico",
        nombre="Base genérica",
        account_id=None,
        connection=PG_DSN,
    )

    row = db.fetch_one("SELECT * FROM projects WHERE id = ?", (pid,))
    assert row["provider"] == "postgres"
    assert row["project_ref"] == ""
    assert row["account_id"] == accounts_srv.ensure_default_group()
    assert json.loads(row["backup_options"]) == {
        "no_owner": True,
        "no_privileges": True,
    }


def test_proyecto_supabase_exige_cuenta(db):
    with pytest.raises(ProjectError):
        create_project(
            slug="sb-sin-cuenta",
            nombre="Supabase",
            account_id=None,
            connection=PG_DSN,
            project_ref="abcdefghij",
            provider="supabase",
        )


def test_proveedor_inferido_por_la_referencia(db):
    account_id = accounts_srv.create_account("Cuenta SB", "sbp_token", provider="supabase")
    pid = create_project(
        slug="sb-inferido",
        nombre="Supabase",
        account_id=account_id,
        connection=PG_DSN,
        project_ref="abcdefghij",
    )
    assert get_by_slug("sb-inferido")["provider"] == "supabase"
    assert db.fetch_one("SELECT provider FROM projects WHERE id = ?", (pid,))["provider"] == "supabase"


def test_cuenta_de_otro_proveedor_se_rechaza(db):
    account_id = accounts_srv.create_account("Cuenta SB", "sbp_token", provider="supabase")
    with pytest.raises(ProjectError):
        create_project(
            slug="pg-mismatch",
            nombre="Base genérica",
            account_id=account_id,
            connection=PG_DSN,
            provider="postgres",
        )


def test_conexion_debe_ser_uri_de_postgresql(db):
    with pytest.raises(ProjectError):
        create_project(
            slug="dsn-invalido",
            nombre="Base genérica",
            account_id=None,
            connection="mysql://usuario:clave@host/base",
        )


def test_list_projects_filtra_por_proveedor(db):
    account_id = accounts_srv.create_account("Cuenta SB", "sbp_token", provider="supabase")
    create_project(
        slug="pg-uno", nombre="PG", account_id=None, connection=PG_DSN,
    )
    create_project(
        slug="sb-uno", nombre="SB", account_id=account_id,
        connection=PG_DSN, project_ref="ref12345678",
    )

    solo_pg = list_projects(provider="postgres")
    solo_sb = list_projects(provider="supabase")

    assert [p["slug"] for p in solo_pg] == ["pg-uno"]
    assert [p["slug"] for p in solo_sb] == ["sb-uno"]


def test_cambiar_a_postgres_reasigna_grupo_y_limpia_ref(db):
    account_id = accounts_srv.create_account("Cuenta SB", "sbp_token", provider="supabase")
    pid = create_project(
        slug="convertido", nombre="SB", account_id=account_id,
        connection=PG_DSN, project_ref="ref12345678",
    )

    update_project(pid, provider="postgres")

    row = db.fetch_one("SELECT provider, account_id, project_ref FROM projects WHERE id = ?", (pid,))
    assert row["provider"] == "postgres"
    assert row["account_id"] == accounts_srv.ensure_default_group()
    assert row["project_ref"] == ""
    assert update_project(pid, provider="postgres") is None


def test_actualizar_sin_cron_conserva_el_actual(db):
    pid = create_project(
        slug="con-cron", nombre="PG", account_id=None,
        connection=PG_DSN, schedule="30 3 * * *",
    )

    update_project(pid, nombre="Renombrado", schedule=None)

    row = db.fetch_one("SELECT nombre, schedule FROM projects WHERE id = ?", (pid,))
    assert row["nombre"] == "Renombrado"
    assert row["schedule"] == "30 3 * * *"


def test_opciones_de_backup_personalizadas(db):
    pid = create_project(
        slug="sin-owner", nombre="PG", account_id=None, connection=PG_DSN,
        backup_options={"no_owner": False, "no_privileges": True},
    )
    project = get_by_slug("sin-owner")
    assert project["id"] == pid
    assert project["backup_options"] == {"no_owner": False, "no_privileges": True}


def test_opcion_de_backup_desconocida_se_rechaza(db):
    with pytest.raises(ProjectError):
        create_project(
            slug="opcion-mala", nombre="PG", account_id=None, connection=PG_DSN,
            backup_options={"no_owner": True, "drop_tables": True},
        )


def test_grupos_postgres_se_deduplican_por_nombre(db):
    primero = accounts_srv.create_account("Equipo", "", provider="postgres")
    segundo = accounts_srv.create_account("Equipo", "", provider="postgres")
    assert primero == segundo

    cuenta = accounts_srv.get_account(primero)
    assert cuenta["provider"] == "postgres"
    assert cuenta["has_pat"] is False
    assert cuenta["pat_masked"] == "(sin PAT)"


def test_cuenta_supabase_sin_pat_se_rechaza(db):
    with pytest.raises(accounts_srv.AccountError):
        accounts_srv.create_account("Sin token", "", provider="supabase")


def test_proveedor_de_cuenta_invalido(db):
    with pytest.raises(accounts_srv.AccountError):
        accounts_srv.create_account("Rara", "x", provider="mysql")


def test_list_accounts_incluye_el_proveedor(db):
    accounts_srv.create_account("Cuenta SB", "sbp_token", provider="supabase")
    accounts_srv.ensure_default_group()

    providers = {a["provider"] for a in accounts_srv.list_accounts()}
    assert providers == {"supabase", "postgres"}
