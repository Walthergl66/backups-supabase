"""Cliente de la Management API de Supabase.

Valida PATs, lista proyectos y obtiene connection strings desde la API
oficial de Supabase. Todas las funciones son bloqueantes (usar con
`asyncio.to_thread` desde el bot).
"""

from __future__ import annotations

import logging

import httpx

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
        return False, f"No se pudo contactar la Management API: {exc}"
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


def get_connection_string(pat: str, project_ref: str) -> str | None:
    """Obtiene la connection string (pooler) de un proyecto.

    Devuelve la cadena de conexión o None si no está disponible.
    """
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
    try:
        resp = httpx.get(
            f"{SUPABASE_API}/v1/projects/{project_ref}/config/database/pooler",
            headers=headers,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        logger.warning("Error al obtener connection string: %s", exc)
        return None
    if resp.status_code == 200:
        poolers = resp.json()
        for pooler in poolers:
            if pooler.get("database_type") == "PRIMARY":
                return pooler.get("connection_string") or pooler.get("connectionString")
        if poolers:
            return poolers[0].get("connection_string") or poolers[0].get("connectionString")
    logger.warning(
        "No se pudo obtener connection string para %s: HTTP %s",
        project_ref, resp.status_code,
    )
    return None
