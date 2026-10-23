"""Proveedor PostgreSQL genérico.

No asume Supabase: valida una URI `postgresql://`, prueba la conexión con
`psql` y expone las credenciales como variables de entorno para que ni
`psql` ni `pg_dump` reciban la contraseña por `argv`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from urllib.parse import parse_qs, unquote, urlparse

from services.pg_errors import friendly_db_error
from services.providers.base import ConnectionTest, ProviderCapabilities

capabilities = ProviderCapabilities(
    name="postgres",
    label="PostgreSQL",
    supports_import=False,
    supports_cloud_status=False,
    requires_pat=False,
)


def parse_dsn(connection: str) -> dict:
    """Descompone una URI de PostgreSQL en sus piezas (contraseña incluida)."""
    parsed = urlparse((connection or "").strip())
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError("La conexión debe empezar por 'postgresql://' o 'postgres://'.")
    if not parsed.hostname:
        raise ValueError("La conexión no incluye un host válido.")
    query = parse_qs(parsed.query)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "dbname": unquote(parsed.path.lstrip("/")) or None,
        "sslmode": query.get("sslmode", [None])[0],
    }


def validate_dsn(connection: str) -> tuple[bool, str]:
    """Valida la forma de la URI sin abrir conexión."""
    try:
        data = parse_dsn(connection)
    except ValueError as exc:
        return False, str(exc)
    if not data["dbname"]:
        return False, "La conexión debe incluir el nombre de la base de datos (/basedatos)."
    return True, "Cadena de conexión válida."


def psql_env(connection: str, timeout: int = 15) -> dict[str, str]:
    """Variables de entorno de libpq para no exponer la contraseña en argv."""
    data = parse_dsn(connection)
    env = {
        "PGCONNECT_TIMEOUT": str(max(1, int(timeout))),
        "PGAPPNAME": "supabase-backups",
    }
    if data["password"]:
        env["PGPASSWORD"] = data["password"]
    if data["sslmode"]:
        env["PGSSLMODE"] = data["sslmode"]
    return env


def psql_command(connection: str, query: str) -> list[str]:
    """Argumentos de psql con host/puerto/usuario/BD por separado."""
    data = parse_dsn(connection)
    args = ["psql", "--no-psqlrc", "--tuples-only", "--no-align", "--field-separator", "|"]
    args += ["--host", str(data["host"]), "--port", str(data["port"])]
    if data["user"]:
        args += ["--username", str(data["user"])]
    if data["dbname"]:
        args += ["--dbname", str(data["dbname"])]
    args += ["--command", query]
    return args


def _run_psql(connection: str, query: str, timeout: int) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(psql_env(connection, timeout))
    return subprocess.run(
        psql_command(connection, query),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
        check=False,
        env=env,
    )


def test_connection(connection: str, timeout: int = 15) -> ConnectionTest:
    """Prueba la conexión y devuelve base, host y versión del servidor."""
    ok_shape, shape_detail = validate_dsn(connection)
    if not ok_shape:
        return ConnectionTest(ok=False, detalle=shape_detail)
    if shutil.which("psql") is None:
        return ConnectionTest(
            ok=True,
            detalle="verificación omitida (psql no está instalado)",
        )

    data = parse_dsn(connection)
    start = time.monotonic()
    query = "SELECT current_database(), current_setting('server_version')"
    try:
        proc = _run_psql(connection, query, timeout)
    except subprocess.TimeoutExpired:
        return ConnectionTest(
            ok=False,
            detalle="la conexión tardó demasiado y se canceló",
            host=data["host"],
            database=data["dbname"],
        )
    except OSError as exc:
        return ConnectionTest(
            ok=False,
            detalle=f"No se pudo lanzar psql: {exc}",
            host=data["host"],
            database=data["dbname"],
        )

    latency = round((time.monotonic() - start) * 1000, 1)
    if proc.returncode != 0:
        return ConnectionTest(
            ok=False,
            detalle=friendly_db_error(proc.stderr or "psql no pudo conectar."),
            host=data["host"],
            database=data["dbname"],
            latency_ms=latency,
        )

    database = data["dbname"]
    version = None
    line = (proc.stdout or "").strip().splitlines()
    if line:
        parts = line[0].split("|")
        if parts:
            database = parts[0] or database
        if len(parts) > 1:
            version = parts[1]
    return ConnectionTest(
        ok=True,
        detalle=f"conexión correcta a {database} ({data['host']})",
        host=data["host"],
        database=database,
        server_version=version,
        latency_ms=latency,
    )


def cloud_status(project_ref: str, pat: str) -> tuple[bool, str]:
    """PostgreSQL genérico no tiene estado cloud: no aplica."""
    return True, ""
