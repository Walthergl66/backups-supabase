"""Contratos comunes de los proveedores de base de datos.

Un proveedor describe de dónde sale la conexión y qué capacidades extra
ofrece (importación, estado cloud). El backup en sí es siempre el mismo:
`pg_dump` contra la URI de PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str
    label: str
    supports_import: bool = False
    supports_cloud_status: bool = False
    requires_pat: bool = False


@dataclass
class ConnectionTest:
    ok: bool
    detalle: str = ""
    host: str | None = None
    database: str | None = None
    server_version: str | None = None
    latency_ms: float | None = None
