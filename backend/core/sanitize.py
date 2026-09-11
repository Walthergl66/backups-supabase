"""Saneado de secretos en textos que acaban en logs, historial o Telegram.

La idea es un safety-net: ocultar patrones de credenciales antes de que una
cadena (stderr de psql/pg_dump, errores HTTP, librerías) llegue a un mensaje
o log. Es defensivo: los flujos correctos nunca deberían exponer secretos.
"""

from __future__ import annotations

import re

# postgres://user:password@host:5432/db  ->  postgres://user:••••@host:5432/db
_URI_USERINFO = re.compile(r"(?i)([a-z][a-z0-9+.\-]*://)([^:/@\s]+):([^@\s]+)@")

# PAT de Supabase: sbp_xxxxxxxx...
_PAT = re.compile(r"\b(sbp_[^\s]{8,})\b")

# password = 'valor'  (formato que puede aparecer en cadenas SQL/DSN)
_PASSWORD_EQ = re.compile(r"(?i)(\bpassword\s*=\s*['\"]?)[^\s'\"&;]+")

MASK = "••••"


def redact_secrets(text: str | None) -> str:
    """Oculta credenciales reconocibles en un texto. Nunca lanza."""
    if not text:
        return text or ""
    text = _URI_USERINFO.sub(lambda m: f"{m.group(1)}{m.group(2)}:{MASK}@", text)
    text = _PAT.sub(f"sbp_{MASK}", text)
    text = _PASSWORD_EQ.sub(lambda m: f"{m.group(1)}{MASK}", text)
    return text