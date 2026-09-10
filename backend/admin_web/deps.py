"""Dependencias de la API (autenticación JWT por Bearer)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from core import jwt


def _unauthorized(detail: str = "Se requiere autenticación.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise _unauthorized()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("Token Bearer inválido o ausente.")
    try:
        claims = jwt.decode_token(token.strip())
    except jwt.InvalidToken as exc:
        raise _unauthorized(f"Token inválido: {exc}") from exc
    return {
        "id": int(claims["sub"]),
        "username": claims["username"],
        "rol": claims["rol"],
    }


def require_admin(user: dict = None) -> dict:
    """Dependencia combinable: llama después de `current_user`."""
    if user is None:
        raise _unauthorized()
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Necesitas el rol admin para realizar esta acción.",
        )
    return user