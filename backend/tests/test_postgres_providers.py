"""Tests de los proveedores, el parseo de DSN y los errores de PostgreSQL."""

from pathlib import Path

from services import providers
from services.pg_errors import friendly_db_error
from services.providers import postgres


def test_registro_de_proveedores():
    nombres = {p["name"] for p in providers.list_providers()}
    assert nombres == {"postgres", "supabase"}

    assert providers.get_provider(None).capabilities.name == "postgres"
    assert providers.get_provider("desconocido").capabilities.name == "postgres"

    supabase = providers.get_provider("supabase")
    assert supabase.capabilities.supports_import is True
    assert supabase.capabilities.supports_cloud_status is True
    assert supabase.capabilities.requires_pat is True

    directo = providers.get_provider("postgres")
    assert directo.capabilities.supports_import is False
    assert directo.capabilities.requires_pat is False


def test_cloud_status_no_aplica_a_postgres():
    ok, detalle = providers.cloud_status({"provider": "postgres"})
    assert ok is True
    assert "no aplica" in detalle


def test_parse_dsn_descompone_y_decodifica():
    data = postgres.parse_dsn(
        "postgresql://alice:p%40ss@db.example.com:6543/mi%20base?sslmode=require"
    )
    assert data == {
        "host": "db.example.com",
        "port": 6543,
        "user": "alice",
        "password": "p@ss",
        "dbname": "mi base",
        "sslmode": "require",
    }


def test_parse_dsn_puerto_por_defecto():
    data = postgres.parse_dsn("postgres://user:pass@host/db")
    assert data["port"] == 5432
    assert data["sslmode"] is None


def test_validate_dsn():
    ok, _ = postgres.validate_dsn("postgresql://user:pass@host:5432/db")
    assert ok is True

    ok, detalle = postgres.validate_dsn("mysql://user:pass@host/db")
    assert ok is False and "postgresql" in detalle

    ok, detalle = postgres.validate_dsn("postgresql://host")
    assert ok is False and "base de datos" in detalle


def test_psql_env_no_pone_la_clave_en_argv():
    connection = "postgresql://user:s3cr3t@host:5432/db?sslmode=require"
    env = postgres.psql_env(connection, timeout=7)

    assert env["PGPASSWORD"] == "s3cr3t"
    assert env["PGSSLMODE"] == "require"
    assert env["PGCONNECT_TIMEOUT"] == "7"

    args = postgres.psql_command(connection, "SELECT 1")
    assert "s3cr3t" not in " ".join(args)
    assert "--host" in args and "--username" in args and "--dbname" in args


def test_psql_env_sin_password():
    env = postgres.psql_env("postgresql://host/db")
    assert "PGPASSWORD" not in env


def test_dump_command_usa_entorno_y_opciones(db):
    from backup import runner

    args, env = runner._dump_command(
        "postgresql://alice:s3cr3t@db.example.com:6543/app?sslmode=require",
        Path("/tmp/salida.dump"),
        {"no_owner": True, "no_privileges": True},
    )

    assert "s3cr3t" not in " ".join(args)
    assert env["PGPASSWORD"] == "s3cr3t"
    assert env["PGSSLMODE"] == "require"
    assert "--no-owner" in args
    assert "--no-privileges" in args
    assert "--format=custom" in args
    assert "db.example.com" in args
    assert "6543" in args
    assert "app" in args


def test_dump_command_sin_opciones(db):
    from backup import runner

    args, _ = runner._dump_command(
        "postgresql://u:p@h:5432/d", Path("/tmp/x.dump"), {}
    )
    assert "--no-owner" not in args
    assert "--no-privileges" not in args


def test_dump_command_compatible_con_dsn_antiguo(db):
    from backup import runner

    legacy = "host=db.example.com port=5432 user=u password=p dbname=d"
    args, env = runner._dump_command(legacy, Path("/tmp/x.dump"), {})

    assert "--dbname" in args
    assert legacy in args
    assert "PGPASSWORD" not in env


def test_errores_amigables_de_postgresql():
    assert "contraseña" in friendly_db_error('FATAL: password authentication failed for user "u"')
    assert "no existe" in friendly_db_error('FATAL: role "u" does not exist')
    assert "no coincide" in friendly_db_error('FATAL: database "x" does not exist')
    assert "resolver" in friendly_db_error("could not translate host name")
    assert "tardó demasiado" in friendly_db_error("connection timed out")
    assert "rechazó" in friendly_db_error("connection refused")
    assert "pg_hba.conf" in friendly_db_error('no pg_hba.conf entry for host "1.2.3.4"')
    assert "límite de conexiones" in friendly_db_error("FATAL: too many connections")
    assert "pg_dump" in friendly_db_error("aborting because of server version mismatch")
    assert "SSL" in friendly_db_error("SSL error: certificate verify failed")
    assert "no se pudo conectar" in friendly_db_error("algo raro")
