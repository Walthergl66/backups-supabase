"""Registro de proveedores soportados (PostgreSQL genérico y Supabase)."""

from __future__ import annotations

from services.providers import postgres, supabase

_PROVIDERS = {
    postgres.capabilities.name: postgres,
    supabase.capabilities.name: supabase,
}


def get_provider(name: str | None):
    """Devuelve el módulo del proveedor; PostgreSQL genérico por defecto."""
    key = (name or "postgres").strip().lower()
    return _PROVIDERS.get(key, postgres)


def provider_for_project(project: dict):
    return get_provider(project.get("provider"))


def list_providers() -> list[dict]:
    return [
        {
            "name": provider.capabilities.name,
            "label": provider.capabilities.label,
            "supports_import": provider.capabilities.supports_import,
            "supports_cloud_status": provider.capabilities.supports_cloud_status,
            "requires_pat": provider.capabilities.requires_pat,
        }
        for provider in _PROVIDERS.values()
    ]


def cloud_status(project: dict, pat: str = "") -> tuple[bool, str]:
    """Estado cloud, si el proveedor lo soporta; si no, se omite."""
    provider = provider_for_project(project)
    if not provider.capabilities.supports_cloud_status:
        return True, "estado cloud no aplica a este proveedor"
    return provider.cloud_status(project.get("project_ref") or "", pat)
