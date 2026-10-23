"""Proveedor Supabase: conserva la importación por PAT y el estado cloud."""

from __future__ import annotations

from services import supabase_api as _api
from services.providers.base import ConnectionTest, ProviderCapabilities
from services.providers import postgres as _postgres

capabilities = ProviderCapabilities(
    name="supabase",
    label="Supabase",
    supports_import=True,
    supports_cloud_status=True,
    requires_pat=True,
)


def validate_pat(pat: str) -> tuple[bool, str]:
    return _api.validate_pat(pat)


def list_projects(pat: str) -> list[dict]:
    return _api.list_projects(pat)


def get_connection_string(
    pat: str,
    project_ref: str,
    mode: str = "session",
    password: str | None = None,
) -> str | None:
    return _api.get_connection_string(pat, project_ref, mode=mode, password=password)


def test_connection(connection: str, timeout: int = 15) -> ConnectionTest:
    """La conexión a la base es PostgreSQL estándar (pooler o directa)."""
    return _postgres.test_connection(connection, timeout=timeout)


def cloud_status(project_ref: str, pat: str) -> tuple[bool, str]:
    """Consulta el estado del proyecto en la Management API de Supabase."""
    from backup import monitor

    return monitor.check_supabase_api(project_ref, pat)
