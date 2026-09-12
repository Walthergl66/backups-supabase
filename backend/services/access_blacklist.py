"""Lista negra en memoria de access tokens (JWT) revocados.

El access token es corto (JWT_TTL_MINUTES, 60 por defecto) y sin estado.
Al hacer logout se revoca su `jti` para invalidarlo de inmediato (no solo
cuando expira). La lista vive en memoria, como los refresh tokens: este
proyecto corre un único proceso y reiniciarlo vacía la lista (los tokens
siguen firmados y vigentes solo hasta su expiración).
"""

from __future__ import annotations

import threading
import time

_COOLDOWN_REFRESH_SECONDS = 60


class AccessBlacklist:
    def __init__(self, max_size: int = 5000) -> None:
        self._entries: dict[str, int] = {}  # jti -> exp (epoch)
        self._lock = threading.Lock()
        self._max_size = max_size
        self._last_prune = 0.0

    def revoke(self, jti: str, exp: int) -> None:
        with self._lock:
            self._prune_locked(time.time())
            if len(self._entries) >= self._max_size:
                self._entries.clear()
            self._entries[jti] = exp

    def is_revoked(self, jti: str | None) -> bool:
        if not jti:
            return False
        with self._lock:
            self._prune_locked(time.time())
            return jti in self._entries

    def _prune_locked(self, now: float) -> None:
        # La poda es barata y se ejecuta como mucho una vez por minuto.
        if now - self._last_prune < _COOLDOWN_REFRESH_SECONDS:
            return
        self._last_prune = now
        expired = [k for k, exp in self._entries.items() if exp < now]
        for k in expired:
            del self._entries[k]


blacklist = AccessBlacklist()