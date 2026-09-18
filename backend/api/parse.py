"""Helpers de parsing para la API (JSON de entrada desde el frontend)."""

from __future__ import annotations


def as_bool(value, default: bool = False) -> bool:
    """Convierte a booleano un valor que puede llegar como bool, número o cadena.

    `bool("false")` evalúa a True por accidente; aquí "false"/"0"/"no" son False
    y "true"/"1"/"si" son True. Valores desconocidos caen a `default`.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on", "si"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default