"""Cliente de la Management API de Supabase.

Valida PATs, lista proyectos y obtiene connection strings desde la API
oficial de Supabase. Todas las funciones son bloqueantes (usar con
`asyncio.to_thread` desde el bot).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from urllib.parse import quote, urlparse, urlunparse

import httpx

from core import sanitize

logger = logging.getLogger(__name__)

SUPABASE_API = "https://api.supabase.com"


def validate_pat(pat: str) -> tuple[bool, str]:
    """Valida un PAT haciendo GET /v1/projects.

    Devuelve (es_valido, mensaje).
    """
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
    try:
        resp = httpx.get(f"{SUPABASE_API}/v1/projects", headers=headers, timeout=15)
    except httpx.HTTPError as exc:
        return False, sanitize.redact_secrets(f"No se pudo contactar la Management API: {exc}")
    if resp.status_code == 200:
        return True, "PAT válido."
    if resp.status_code in (401, 403):
        return False, "El PAT no es válido o no tiene permisos."
    return False, f"La Management API respondió HTTP {resp.status_code}."


def list_projects(pat: str) -> list[dict]:
    """Lista los proyectos del usuario asociados al PAT.

    Devuelve una lista de diccionarios con keys: ref, name, status, region.
    Lanza httpx.HTTPError si falla la conexión.
    """
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
    resp = httpx.get(f"{SUPABASE_API}/v1/projects", headers=headers, timeout=15)
    resp.raise_for_status()
    projects = resp.json()
    return [
        {
            "ref": p.get("id") or p.get("ref", ""),
            "name": p.get("name", ""),
            "status": p.get("status", "unknown"),
            "region": p.get("region", ""),
        }
        for p in projects
    ]


def get_connection_string(
    pat: str,
    project_ref: str,
    mode: str = "session",
    password: str | None = None,
) -> str | None:
    """Obtiene la connection string (pooler) de un proyecto.

    `mode` selecciona el pooler: "session" (:5432, recomendado para pg_dump)
    o "transaction" (:6543). Si `password` se entrega, se inyecta en la URL
    reemplazando el marcador [YOUR-PASSWORD]. Devuelve la cadena o None.
    """
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
    try:
        resp = httpx.get(
            f"{SUPABASE_API}/v1/projects/{project_ref}/config/database/pooler",
            headers=headers,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        logger.warning("Error al obtener connection string: %s", sanitize.redact_secrets(str(exc)))
        return None
    if resp.status_code == 200:
        poolers = resp.json()
        pooler = _pick_pooler(poolers, mode)
        if pooler is not None:
            raw = pooler.get("connection_string") or pooler.get("connectionString") or ""
            if raw:
                return _inject_password(raw, password)
    logger.warning(
        "No se pudo obtener connection string para %s: HTTP %s",
        project_ref, resp.status_code,
    )
    return None


def _pick_pooler(poolers: list[dict], mode: str) -> dict | None:
    """Elige la entrada del pooler que coincide con el modo pedido.

    La respuesta de Supabase es una lista de poolers (PRIMARY/REPLICA, con
    modo session/transaction). Si no hay coincidencia exacta se usa el
    primero con database_type PRIMARY; si nada, el primero.
    """
    wanted = mode.lower()
    for p in poolers:
        pool_mode = str(p.get("pool_mode") or p.get("mode") or "").lower()
        if pool_mode == wanted and p.get("database_type") == "PRIMARY":
            return p
    for p in poolers:
        pool_mode = str(p.get("pool_mode") or p.get("mode") or "").lower()
        if pool_mode == wanted:
            return p
    for p in poolers:
        if p.get("database_type") == "PRIMARY":
            return p
    return poolers[0] if poolers else None


def _inject_password(connection: str, password: str | None) -> str:
    """Inserta la contraseña (URL-encoded) en la connection string.

    Reemplaza el marcador `[YOUR-PASSWORD]` que devuelve Supabase, o si la
    URL ya trae un userinfo, reemplaza la contraseña existente.
    """
    if not password:
        return connection
    encoded = quote(password, safe="")
    if "[YOUR-PASSWORD]" in connection:
        return connection.replace("[YOUR-PASSWORD]", encoded)
    parsed = urlparse(connection)
    if parsed.hostname is None:
        return connection
    user = parsed.username or "postgres"
    host = parsed.hostname
    netloc = f"{user}:{encoded}@{host}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def friendly_db_error(stderr: str) -> str:
    """Traduce el stderr de psql a un mensaje amigable para el usuario."""
    low = stderr.lower()
    if "password authentication failed" in low or "no password supplied" in low:
        return "la contraseña o el usuario de la base de datos son incorrectos"
    if 'role "' in low and "does not exist" in low:
        return "el usuario de la base de datos no existe"
    if "does not exist" in low or "not found" in low:
        return "el nombre de la base de datos no coincide con el proyecto"
    if "could not translate host name" in low or "name or service not known" in low or "getaddrinfo" in low:
        return "no se pudo resolver el servidor (revisa la URL o tu conexión a internet)"
    if "timed out" in low or "timeout" in low or "time out" in low:
        return "la conexión tardó demasiado y se canceló (probablemente tu red bloquea este servidor)"
    if "connection refused" in low:
        return "el servidor rechazó la conexión (puede estar apagado o bloqueado)"
    if "ssl" in low:
        return "falló el cifrado SSL de la conexión"
    return "no se pudo conectar con el servidor de base de datos"


def test_connection(connection: str, timeout: int = 15) -> tuple[bool, str]:
    """Prueba la cadena contra el pooler con `psql` (SELECT 1).

    Devuelve (ok, detalle). Si psql no está disponible la verificación se
    omite (no es un fallo del proyecto).
    """
    if shutil.which("psql") is None:
        return True, "verificación omitida (psql no está instalado)"
    try:
        proc = subprocess.run(
            ["psql", connection, "-tA", "-c", "SELECT 1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, friendly_db_error(str(exc))
    if proc.returncode == 0:
        return True, (proc.stdout or "").strip()
    return False, friendly_db_error(proc.stderr or "psql no pudo conectar.")
