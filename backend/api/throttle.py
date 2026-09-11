"""Mini-WAF por IP (A5): corta escaneos y ráfagas anómalas hacia /api/*.

Complementa a slowapi (enfocado en login): vigila el TRÁFICO GLOBAL por IP en
una ventana deslizante y bloquea temporalmente al IP que lo supere, avisando
por Telegram a los admins (a lo sumo una alerta cada 5 minutos).
"""

from __future__ import annotations

import threading
import time

from core.config import settings

_ALERT_COOLDOWN_SECONDS = 300
_last_alert_at = 0.0
_alert_lock = threading.Lock()


class IpThrottle:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def hit(self, ip: str) -> bool:
        """Registra una petición. True solo en la petición que CRUZA el umbral."""
        now = time.time()
        window = float(settings().throttle_window_seconds)
        with self._lock:
            self._prune_if_large(now, window)
            if self._blocked_until.get(ip, 0) > now:
                return False
            hits = [t for t in self._hits.get(ip, []) if now - t <= window]
            hits.append(now)
            self._hits[ip] = hits
            if len(hits) > settings().throttle_max_requests:
                self._blocked_until[ip] = now + settings().throttle_block_seconds
                self._hits.pop(ip, None)
                return True
            return False

    def is_blocked(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            return self._blocked_until.get(ip, 0) > now

    def _prune_if_large(self, now: float, window: float) -> None:
        if len(self._hits) > 5000:
            self._hits = {
                k: [t for t in v if now - t <= window] for k, v in self._hits.items()
            }


throttle = IpThrottle()


def should_notify_scan() -> bool:
    global _last_alert_at
    with _alert_lock:
        now = time.time()
        if now - _last_alert_at < _ALERT_COOLDOWN_SECONDS:
            return False
        _last_alert_at = now
        return True