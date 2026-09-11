"""Refresh tokens para la API web (M6).

El access token (JWT) es corto y viaja en `Authorization: Bearer`. La sesión
de larga duración vive en un *refresh token* opaco guardado en cookie
`HttpOnly` (inaccesible a JS), que se rota en cada uso y expira tras 7 días
por defecto. En memoria (un solo proceso, un solo contenedor), igual que las
sesiones web.
"""

from __future__ import annotations

import secrets
import threading
import time

from core.config import settings


class RefreshTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, user: dict) -> str:
        token = secrets.token_urlsafe(48)
        with self._lock:
            self._purge()
            self._tokens[token] = {
                "user_id": user["id"],
                "username": user["username"],
                "rol": user["rol"],
                "created_at": time.time(),
            }
        return token

    def validate_and_rotate(self, token: str) -> tuple[str, dict] | None:
        """Valida el token; si es válido lo invalida y emite uno nuevo (rotación)."""
        with self._lock:
            self._purge()
            entry = self._tokens.pop(token, None)
            if entry is None:
                return None
        user = {
            "id": entry["user_id"],
            "username": entry["username"],
            "rol": entry["rol"],
        }
        new_token = self.create(user)
        return new_token, entry

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    def _purge(self) -> None:
        now = time.time()
        ttl = settings().refresh_ttl_seconds
        expired = [
            t for t, e in self._tokens.items() if now - e["created_at"] > ttl
        ]
        for t in expired:
            self._tokens.pop(t, None)


refresh_store = RefreshTokenStore()