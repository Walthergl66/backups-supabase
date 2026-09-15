"""Refresh tokens para la API web (M6).

El access token (JWT) es corto y viaja en `Authorization: Bearer`. La sesión
de larga duración vive en un *refresh token* opaco guardado en cookie
`HttpOnly` (inaccesible a JS), que se rota en cada uso y expira tras 7 días
por defecto.

Los tokens se persisten en SQLite (tabla `refresh_sessions`) para que las
sesiones sobrevivan a reinicios del contenedor. Solo se guarda el hash
SHA-256 del token, nunca el token en claro, de modo que un volcado de la BD
no exponga credenciales utilizables.
"""

from __future__ import annotations

import hashlib
import secrets
import time

from core import db
from core.config import settings


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RefreshTokenStore:
    def create(self, user: dict) -> str:
        """Crea una sesión y devuelve el token en claro (única vez que existe)."""
        token = secrets.token_urlsafe(48)
        now = time.time()
        db.execute(
            """
            INSERT INTO refresh_sessions (token_hash, user_id, username, rol, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_hash_token(token), user["id"], user["username"], user["rol"],
             now, now + settings().refresh_ttl_seconds),
        )
        self._purge_expired()
        return token

    def validate_and_rotate(self, token: str) -> tuple[str, dict] | None:
        """Valida el token; si es válido lo invalida y emite uno nuevo (rotación)."""
        if not token:
            return None
        self._purge_expired()
        token_hash = _hash_token(token)
        row = db.fetch_one(
            "SELECT user_id, username, rol FROM refresh_sessions WHERE token_hash = ? AND expires_at > ?",
            (token_hash, time.time()),
        )
        if row is None:
            return None
        db.execute("DELETE FROM refresh_sessions WHERE token_hash = ?", (token_hash,))
        entry = {
            "id": row["user_id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "rol": row["rol"],
        }
        new_token = self.create(entry)
        return new_token, entry

    def revoke(self, token: str) -> None:
        if not token:
            return
        db.execute("DELETE FROM refresh_sessions WHERE token_hash = ?", (_hash_token(token),))

    def _purge_expired(self) -> None:
        """Borra sesiones vencidas (se invoca al crear una nueva)."""
        db.execute("DELETE FROM refresh_sessions WHERE expires_at <= ?", (time.time(),))


refresh_store = RefreshTokenStore()