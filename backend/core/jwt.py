"""Tokens JWT (HS256) con la stdlib, para la API del frontend.

Se usa un token sin estado en el header `Authorization: Bearer <token>`:
evita cookies/CSRF entre servicios (backend y frontend separados). La clave
de firma es `SESSION_SECRET` del entorno.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from core.config import settings

TOKEN_TTL_SECONDS = 12 * 3600  # 12 h, igual que las sesiones web antiguas
_ISSUER = "supabase-backups"

_b64 = base64.urlsafe_b64encode


def _b64url(data: bytes) -> str:
    return _b64(data).rstrip(b"=").decode("ascii")


def _b64decode(part: str) -> bytes:
    pad = "=" * (-len(part) % 4)
    return base64.urlsafe_b64decode(part + pad)


def _sign(data: bytes) -> str:
    return _b64url(
        hmac.new(settings().session_secret.encode("utf-8"), data, hashlib.sha256).digest()
    )


def _encode(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    return f"{header_part}.{payload_part}.{_sign(signing_input)}"


def create_token(user: dict, ttl: int | None = None) -> str:
    now = int(time.time())
    payload = {
        "iss": _ISSUER,
        "sub": str(user["id"]),
        "username": user["username"],
        "rol": user["rol"],
        "iat": now,
        "exp": now + (ttl or TOKEN_TTL_SECONDS),
    }
    return _encode(payload)


class InvalidToken(Exception):
    pass


def decode_token(token: str) -> dict:
    """Valida firma, expiración e issuer; devuelve los claims."""
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidToken("formato inválido")
    header_part, payload_part, signature = parts
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    expected = _sign(signing_input)
    if not hmac.compare_digest(signature, expected):
        raise InvalidToken("firma inválida")
    try:
        payload = json.loads(_b64decode(payload_part))
    except Exception as exc:
        raise InvalidToken("payload inválido") from exc
    if payload.get("iss") != _ISSUER:
        raise InvalidToken("issuer inválido")
    exp = payload.get("exp", 0)
    if int(time.time()) > exp:
        raise InvalidToken("token expirado")
    return payload


def random_token_bytes(n: int = 32) -> str:
    return secrets.token_urlsafe(n)