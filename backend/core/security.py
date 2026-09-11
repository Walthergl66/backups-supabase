"""Seguridad de la interfaz web: hashing de contraseñas, sesiones y CSRF.

Las sesiones viven en memoria (un solo proceso, un solo contenedor), con
tokens aleatorios guardados en cookies firmadas. Contraseñas con PBKDF2-SHA256
y salt por usuario.

Roles web:
  - "admin":  acceso total (CRUD de cuentas, proyectos, usuarios y logs).
  - "viewer": solo lectura.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

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


class SessionStore:
    """Sesiones en memoria con expiración (12 h). No escala a multi-proceso,
    suficiente para el despliegue de un único contenedor."""

    TTL_SECONDS = 12 * 3600

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, username: str, rol: str, user_id: int | None = None) -> str:
        token = secrets.token_urlsafe(48)
        with self._lock:
            self._purge_locked()
            self._sessions[token] = {
                "username": username,
                "rol": rol,
                "id": user_id,
                "created_at": time.time(),
            }
        return token

    def get(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return None
            if time.time() - session["created_at"] > self.TTL_SECONDS:
                self._sessions.pop(token, None)
                return None
            session["created_at"] = time.time()  # deslizante
            return session

    def destroy(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def _purge_locked(self) -> None:
        now = time.time()
        expired = [
            t for t, s in self._sessions.items() if now - s["created_at"] > self.TTL_SECONDS
        ]
        for t in expired:
            self._sessions.pop(t, None)


sessions = SessionStore()


def create_csrf_token(session_token: str) -> str:
    """Token CSRF derivado del secreto global y de la sesión, con giro temporal."""
    raw = f"{settings().csrf_secret}::{session_token}::{time.time() // 600}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_csrf(session_token: str, candidate: str | None) -> bool:
    if not candidate:
        return False
    # Se acepta el token de la ventana actual o de la anterior (giro de 10 min).
    for offset in (0, 1):
        raw = f"{settings().csrf_secret}::{session_token}::{(time.time() // 600) - offset}"
        if hmac.compare_digest(candidate, hashlib.sha256(raw.encode("utf-8")).hexdigest()):
            return True
    return False