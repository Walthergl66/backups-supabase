"""Seguridad de la interfaz web: hashing de contraseñas.

Contraseñas con PBKDF2-SHA256 y salt por usuario; el recuento de iteraciones
se embebe en el hash para poder migrarlo sin relogin.

Roles web:
  - "admin":  acceso total (CRUD de cuentas, proyectos, usuarios y logs).
  - "viewer": solo lectura.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from core.config import settings

# Iteraciones aplicadas a los hashes LEGACY (formato antiguo `salt$digest`,
# sin contador embebido). Los nuevos hashes embeben su recuento.
LEGACY_PBKDF2_ITERATIONS = 260_000


def _active_iterations() -> int:
    return settings().pbkdf2_iterations


def hash_password(password: str) -> str:
    iterations = _active_iterations()
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def _iterations_of(stored: str) -> int:
    """Iteraciones con que se calculó un hash almacenado."""
    if stored.startswith("pbkdf2_sha256$"):
        try:
            return int(stored.split("$")[2])
        except (IndexError, ValueError):
            return _active_iterations()
    return LEGACY_PBKDF2_ITERATIONS


def verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations_s, salt, digest = stored.split("$", 3)
            iterations = int(iterations_s)
        else:
            salt, digest = stored.split("$", 1)
            iterations = LEGACY_PBKDF2_ITERATIONS
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return hmac.compare_digest(candidate.hex(), digest)


def needs_rehash(stored: str) -> bool:
    """True si el hash usa menos iteraciones que las actuales (o es legacy)."""
    return _iterations_of(stored) < _active_iterations()