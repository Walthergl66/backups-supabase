"""Rate limiting de la API (slowapi).

El límite se aplica por IP real del cliente. Detrás del proxy de nginx se
lee `X-Forwarded-For`; únicamente confiamos en él porque el backend no está
publicado a la red (solo es alcanzable a través del contenedor frontend).
"""

from __future__ import annotations

import time
from threading import Lock

from slowapi import Limiter

_RATE_LIMIT_ALERT_COOLDOWN_SECONDS = 300
_last_alert_at = 0.0
_alert_lock = Lock()


def _client_address(request) -> str:
    """IP real del cliente.

    Se usa la ÚLTIMA dirección de `X-Forwarded-For`: los proxies confiables
    (solo nginx vía loopback) RECALCULAN y reenvían un único valor
    verificado, así que el último elemento es el que impone el proxy y no
    puede ser falsificado por el cliente. Sin header, se cae a la IP del
    peer directo.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    if request.client is not None:
        return request.client.host
    return "unknown"


def should_notify_rate_limit() -> bool:
    """True si toca enviar alerta por rate-limit (a lo sumo una cada 5 min)."""
    global _last_alert_at
    with _alert_lock:
        now = time.time()
        if now - _last_alert_at < _RATE_LIMIT_ALERT_COOLDOWN_SECONDS:
            return False
        _last_alert_at = now
        return True


limiter = Limiter(key_func=_client_address)