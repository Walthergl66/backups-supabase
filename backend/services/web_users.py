"""Usuarios de la interfaz web, con roles (admin | viewer)."""

from __future__ import annotations

from datetime import datetime, timedelta

from core import db, security

MAX_FAILED_ATTEMPTS = 8
LOCKOUT_MINUTES = 15


class WebUserError(Exception):
    pass


def _dict(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "rol": row["rol"],
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
    }


def create_web_user(username: str, password: str, rol: str = "admin") -> int:
    username = (username or "").strip()
    rol = rol.strip() if rol.strip() else "admin"
    if not username:
        raise WebUserError("El nombre de usuario es obligatorio.")
    if len(password or "") < 8:
        raise WebUserError("La contraseña debe tener al menos 8 caracteres.")
    if rol not in ("admin", "viewer"):
        raise WebUserError("Rol inválido (admin | viewer).")
    if db.fetch_one("SELECT id FROM web_users WHERE username = ?", (username,)):
        raise WebUserError("Ese nombre de usuario ya existe.")
    return db.execute(
        "INSERT INTO web_users (username, password_hash, rol) VALUES (?, ?, ?)",
        (username, security.hash_password(password), rol),
    )


def get_web_user(username: str) -> dict | None:
    return _dict(db.fetch_one("SELECT * FROM web_users WHERE username = ?", (username,)))


def get_web_user_by_id(user_id: int) -> dict | None:
    return _dict(db.fetch_one("SELECT * FROM web_users WHERE id = ?", (user_id,)))


def list_web_users() -> list[dict]:
    return [_dict(r) for r in db.fetch_all("SELECT * FROM web_users ORDER BY username")]


def authenticate(username: str, password: str) -> dict | None:
    row = db.fetch_one("SELECT * FROM web_users WHERE username = ?", (username.strip(),))
    if row is None or not row["activo"]:
        return None
    if not security.verify_password(password, row["password_hash"]):
        return None
    return _dict(row)


def get_lock_seconds(username: str) -> int:
    """Segundos restantes de bloqueo de una cuenta (0 si no está bloqueada)."""
    row = db.fetch_one(
        "SELECT locked_until FROM web_users WHERE username = ?", (username.strip(),)
    )
    if row is None or not row["locked_until"]:
        return 0
    try:
        end = datetime.fromisoformat(row["locked_until"])
    except ValueError:
        return 0
    return max(0, int((end - datetime.now()).total_seconds()))


def record_failed_login(username: str) -> tuple[int, bool]:
    """Registra un intento fallido y bloquea si se llega al máximo.

    Devuelve (intentos_acumulados, se_bloqueó_ahora).
    No hace nada si el username no existe (evita enumerar cuentas).
    """
    username = username.strip()
    row = db.fetch_one("SELECT id FROM web_users WHERE username = ?", (username,))
    if row is None:
        return 0, False
    db.execute(
        "UPDATE web_users SET failed_attempts = failed_attempts + 1 WHERE username = ?",
        (username,),
    )
    attempts = db.fetch_one(
        "SELECT failed_attempts AS c FROM web_users WHERE username = ?", (username,)
    )["c"]
    if attempts >= MAX_FAILED_ATTEMPTS:
        db.execute(
            "UPDATE web_users SET locked_until = ?, failed_attempts = 0 WHERE username = ?",
            ((datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(), username),
        )
        return attempts, True
    return attempts, False


def reset_failed_logins(username: str) -> None:
    """Limpia los contadores tras un login correcto o una edición del admin."""
    db.execute(
        "UPDATE web_users SET failed_attempts = 0, locked_until = NULL WHERE username = ?",
        (username.strip(),),
    )


def update_web_user(
    user_id: int,
    username: str | None = None,
    password: str | None = None,
    rol: str | None = None,
    activo: bool | None = None,
) -> None:
    current = db.fetch_one("SELECT * FROM web_users WHERE id = ?", (user_id,))
    if current is None:
        raise WebUserError("El usuario no existe.")
    new_username = (username or "").strip() or current["username"]
    if new_username != current["username"]:
        clash = db.fetch_one(
            "SELECT id FROM web_users WHERE username = ? AND id != ?",
            (new_username, user_id),
        )
        if clash is not None:
            raise WebUserError("Ese nombre de usuario ya existe.")
    new_rol = (rol or "").strip() or current["rol"]
    if new_rol not in ("admin", "viewer"):
        raise WebUserError("Rol inválido.")
    if password is not None and password.strip():
        if len(password.strip()) < 8:
            raise WebUserError("La contraseña debe tener al menos 8 caracteres.")
        db.execute(
            "UPDATE web_users SET username = ?, password_hash = ?, rol = ?, activo = ?, "
            "failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (new_username, security.hash_password(password.strip()), new_rol,
             1 if activo is None else int(activo), user_id),
        )
    else:
        db.execute(
            "UPDATE web_users SET username = ?, rol = ?, activo = ?, "
            "failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (new_username, new_rol, 1 if activo is None else int(activo), user_id),
        )


def delete_web_user(user_id: int) -> None:
    total = db.fetch_one("SELECT COUNT(*) AS c FROM web_users WHERE rol = 'admin' AND activo = 1")
    user = db.fetch_one("SELECT rol, activo FROM web_users WHERE id = ?", (user_id,))
    if user and user["rol"] == "admin" and total and total["c"] <= 1:
        raise WebUserError("No se puede eliminar el último administrador activo.")
    db.execute("DELETE FROM web_users WHERE id = ?", (user_id,))


def count_web_users() -> int:
    row = db.fetch_one("SELECT COUNT(*) AS c FROM web_users")
    return row["c"] if row else 0