"""Dependencias de la API (autenticación JWT por Bearer).

Revalida el token CONTRA LA BASE en cada request: si el usuario fue
desactivado, eliminado o bloqueado, o su rol cambió, la sesión vigente
pierde acceso de inmediato (no hay que esperar a que expire el JWT).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from core import jwt
from services import access_blacklist, web_users as web_users_srv


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

    # Token revocado en logout: se invalida de inmediato (no se espera a expirar).
    if access_blacklist.blacklist.is_revoked(claims.get("jti")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada. Vuelve a iniciar sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = web_users_srv.get_web_user_by_id(int(claims["sub"]))
    if user is None or not user["activo"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida: el usuario fue eliminado o desactivado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if web_users_srv.get_lock_seconds(user["username"]) > 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cuenta bloqueada temporalmente por intentos fallidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Rol y nombre SIEMPRE vienen de la BD (los cambios aplican al instante).
    return {
        "id": user["id"],
        "username": user["username"],
        "rol": user["rol"],
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