"""Rate limiting de la API (slowapi).

El límite se aplica por IP real del cliente. Detrás del proxy de nginx se
lee `X-Forwarded-For`; únicamente confiamos en él porque el backend no está
publicado a la red (solo es alcanzable a través del contenedor frontend).
"""

from __future__ import annotations

from slowapi import Limiter


def _client_address(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=_client_address)