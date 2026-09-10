"""Dependencias de la API (autenticación JWT por Bearer)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from core import jwt


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer inválido o ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = jwt.decode_token(token.strip())
    except jwt.InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return {
        "id": int(claims["sub"]),
        "username": claims["username"],
        "rol": claims["rol"],
    }


def require_admin(authorization: str | None = Header(default=None)) -> dict:
    user = get_current_user(authorization)
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Necesitas el rol admin para realizar esta acción.",
        )
    return user


def viewer_allowed(user: dict = None) -> bool:
    """Los operaciones de lectura se permiten a admin y viewer."""
    return True