"""Comprobaciones de estado de un proyecto (conexión y Management API)."""

from __future__ import annotations

import logging
import subprocess

import httpx

logger = logging.getLogger(__name__)

SUPABASE_API = "https://api.supabase.com"


def check_database_connection(conn_str: str) -> tuple[bool, str]:
    """Prueba de conexión a la base vía psql ('SELECT 1').

    Bloqueante; invocarla desde asyncio con `asyncio.to_thread`.
    """
    try:
        proc = subprocess.run(
            ["psql", "--dbname", conn_str, "--tuples-only", "--no-align", "--command", "SELECT 1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        return False, "El binario psql no está disponible (instala postgresql-client)."
    except OSError as exc:
        return False, f"No se pudo lanzar psql: {exc}"
    if proc.returncode == 0:
        return True, "La base de datos responde correctamente."
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return False, "\n".join(tail[-3:]) or "Conexión rechazada."


def check_supabase_api(project_ref: str, pat: str) -> tuple[bool, str]:
    """Consulta el estado del proyecto en la Management API de Supabase.

    Bloqueante (httpx síncrono); usarla con `asyncio.to_thread`.
    """
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
    try:
        resp = httpx.get(f"{SUPABASE_API}/v1/projects/{project_ref}/status", headers=headers, timeout=20)
    except httpx.HTTPError as exc:
        return False, f"No se pudo contactar la Management API: {exc}"
    if resp.status_code == 200:
        data = resp.json()
        status = data.get("status", "desconocido")
        return True, f"Management API: proyecto {project_ref} -> {status}."
    if resp.status_code == 401 or resp.status_code == 403:
        return False, "Management API: el Personal Access Token no es válido o no tiene permisos."
    return False, f"Management API respondió HTTP {resp.status_code}: {resp.text[:300]}"