"""Comprobaciones de estado de un proyecto (conexión y proveedor cloud)."""

from __future__ import annotations

import shutil

import httpx

from services import providers, supabase_api as api_srv

SUPABASE_API = "https://api.supabase.com"


def check_database_connection(conn_str: str) -> tuple[bool, str]:
    """Prueba de conexión a la base vía psql ('SELECT 1'/versión).

    Bloqueante; invocarla desde asyncio con `asyncio.to_thread`. Funciona
    igual para Supabase y para cualquier PostgreSQL.
    """
    if shutil.which("psql") is None:
        return False, "El binario psql no está disponible (instala postgresql-client)."

    result = providers.postgres.test_connection(conn_str, timeout=20)
    if not result.ok:
        return False, result.detalle
    extra = f" · PostgreSQL {result.server_version}" if result.server_version else ""
    return True, f"La base de datos responde correctamente{extra}."


def check_supabase_api(project_ref: str, pat: str) -> tuple[bool, str]:
    """Consulta el estado del proyecto en la Management API de Supabase.

    Solo se invoca para proyectos con proveedor 'supabase'. Bloqueante
    (httpx síncrono); usarla con `asyncio.to_thread`.
    """
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
    try:
        resp = httpx.get(f"{SUPABASE_API}/v1/projects/{project_ref}/status", headers=headers, timeout=20)
    except httpx.HTTPError as exc:
        return False, api_srv._request_error_message(exc)
    if resp.status_code == 200:
        data = resp.json()
        status = data.get("status", "desconocido")
        return True, f"Management API: proyecto {project_ref} -> {status}."
    if resp.status_code in (401, 403):
        return False, "Management API: el Personal Access Token no es válido o no tiene permisos."
    return False, api_srv._http_error_message(resp)
