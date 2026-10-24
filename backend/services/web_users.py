"""Usuarios de la interfaz web, con roles (admin | viewer)."""

from __future__ import annotations

import threading
import time

import pyotp

from core import db, security
from services import refresh_tokens

MAX_FAILED_ATTEMPTS = 8
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 12

# Fallos de login por (usuario, IP). El bloqueo es por IP de origen para que un
# tercero no pueda dejar fuera del panel al dueño de la cuenta desde otra
# dirección (DoS por lockout). Vive en memoria: reiniciar el proceso lo limpia,
# lo cual es aceptable para un control anti fuerza bruta.
_login_failures: dict[tuple[str, str], list[float]] = {}
_login_lock = threading.Lock()


def _failure_key(username: str, ip: str | None) -> tuple[str, str]:
    return ((username or "").strip().lower(), (ip or "").strip())


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
        "totp_enabled": bool(row["totp_enabled"]),
    }


def _get_raw(user_id: int) -> dict | None:
    row = db.fetch_one("SELECT * FROM web_users WHERE id = ?", (user_id,))
    if row is None:
        return None
    return dict(row)


def create_web_user(username: str, password: str, rol: str = "admin") -> int:
    username = (username or "").strip()
    rol = rol.strip() if rol.strip() else "admin"
    if not username:
        raise WebUserError("El nombre de usuario es obligatorio.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise WebUserError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
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
    # Migración progresiva: si el hash usa menos iteraciones que las actuales,
    # se recalcula al vuelo con el estándar y se actualiza en la BD.
    if security.needs_rehash(row["password_hash"]):
        db.execute(
            "UPDATE web_users SET password_hash = ? WHERE id = ?",
            (security.hash_password(password), row["id"]),
        )
    return _dict(row)


def get_lock_seconds(username: str, ip: str | None = None) -> int:
    """Segundos restantes de bloqueo para (usuario, IP) (0 si no está bloqueado).

    Solo se bloquea la combinación usuario + IP de origen: un atacante no puede
    dejar fuera al dueño de la cuenta desde otra dirección.
    """
    key = _failure_key(username, ip)
    window = LOCKOUT_MINUTES * 60
    now = time.time()
    with _login_lock:
        stamps = [t for t in _login_failures.get(key, []) if now - t < window]
        if len(stamps) < MAX_FAILED_ATTEMPTS:
            _login_failures.pop(key, None)
            return 0
        _login_failures[key] = stamps
        return max(0, int((max(stamps) + window) - now))


def record_failed_login(username: str, ip: str | None = None) -> tuple[int, bool]:
    """Registra un intento fallido para (usuario, IP).

    Devuelve (intentos_en_ventana, se_bloqueó_ahora). No distingue si el
    usuario existe: el llamador responde igual en todos los casos.
    """
    key = _failure_key(username, ip)
    window = LOCKOUT_MINUTES * 60
    now = time.time()
    with _login_lock:
        _prune_failures_locked(now, window)
        stamps = [t for t in _login_failures.get(key, []) if now - t < window]
        stamps.append(now)
        _login_failures[key] = stamps
        attempts = len(stamps)
        return attempts, attempts == MAX_FAILED_ATTEMPTS


def reset_failed_logins(username: str, ip: str | None = None) -> None:
    with _login_lock:
        _login_failures.pop(_failure_key(username, ip), None)


def _prune_failures_locked(now: float, window: float) -> None:
    if len(_login_failures) <= 5000:
        return
    for key in list(_login_failures):
        stamps = [t for t in _login_failures[key] if now - t < window]
        if stamps:
            _login_failures[key] = stamps
        else:
            del _login_failures[key]


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
    new_activo = 1 if activo is None else int(activo)
    # No permitir quedarse sin administradores: el último admin activo no
    # puede degradarse a viewer ni desactivarse a sí mismo (mismo criterio
    # que delete_web_user).
    if (
        current["rol"] == "admin"
        and bool(current["activo"])
        and (new_rol != "admin" or not new_activo)
    ):
        total = db.fetch_one(
            "SELECT COUNT(*) AS c FROM web_users WHERE rol = 'admin' AND activo = 1"
        )
        if total and total["c"] <= 1:
            raise WebUserError(
                "No se puede degradar o desactivar al último administrador activo."
            )
    password_changed = password is not None and bool(password.strip())
    if password_changed:
        if len(password.strip()) < MIN_PASSWORD_LENGTH:
            raise WebUserError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
        db.execute(
            "UPDATE web_users SET username = ?, password_hash = ?, rol = ?, activo = ?, "
            "failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (new_username, security.hash_password(password.strip()), new_rol,
             new_activo, user_id),
        )
    else:
        db.execute(
            "UPDATE web_users SET username = ?, rol = ?, activo = ?, "
            "failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (new_username, new_rol, new_activo, user_id),
        )
    # Una contraseña reseteada o una cuenta desactivada invalida de inmediato
    # todas sus sesiones web, sin esperar a la próxima rotación del refresh.
    if password_changed or not new_activo:
        refresh_tokens.refresh_store.revoke_user_sessions(user_id)


def delete_web_user(user_id: int) -> None:
    total = db.fetch_one("SELECT COUNT(*) AS c FROM web_users WHERE rol = 'admin' AND activo = 1")
    user = db.fetch_one("SELECT rol, activo FROM web_users WHERE id = ?", (user_id,))
    if user and user["rol"] == "admin" and total and total["c"] <= 1:
        raise WebUserError("No se puede eliminar el último administrador activo.")
    db.execute("DELETE FROM web_users WHERE id = ?", (user_id,))


def count_web_users() -> int:
    row = db.fetch_one("SELECT COUNT(*) AS c FROM web_users")
    return row["c"] if row else 0


# ---------------------------------------------------------------------------
# TOTP (second-factor authentication)
# ---------------------------------------------------------------------------

TOTP_ISSUER = "Backups Supabase"


def totp_enabled_for(user_id: int) -> bool:
    row = db.fetch_one("SELECT totp_enabled FROM web_users WHERE id = ?", (user_id,))
    return bool(row and row["totp_enabled"])


def generate_totp_secret(user_id: int, code: str | None = None) -> dict:
    """Genera (y guarda pendiente de confirmación) un secreto TOTP para un usuario.

    Nunca desactiva un 2FA ya activo de forma silenciosa: si la cuenta ya
    tiene TOTP habilitado se exige el código actual, y el secreto nuevo queda
    en `totp_pending_secret` sin tocar el secreto en uso hasta el `confirm`.
    Así una sesión capturada sin pasar el 2FA no puede apagar la verificación
    de otro usuario, y quien re-registra su dispositivo no se queda sin factor.
    """
    user = _get_raw(user_id)
    if user is None:
        raise WebUserError("El usuario no existe.")
    if user.get("totp_enabled"):
        if not _totp_valid(user.get("totp_secret") or "", code or ""):
            raise WebUserError("El código TOTP actual es incorrecto o ha caducado.")
    secret = pyotp.random_base32()
    db.execute("UPDATE web_users SET totp_pending_secret = ? WHERE id = ?",
               (secret, user_id))
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user["username"], issuer_name=TOTP_ISSUER
    )
    return {"secret": secret, "otpauth_url": otpauth}


def confirm_totp(user_id: int, code: str) -> None:
    """Valida el código contra el secreto pendiente y activa el 2FA."""
    user = _get_raw(user_id)
    if user is None:
        raise WebUserError("El usuario no existe.")
    if not user.get("totp_pending_secret"):
        raise WebUserError("No hay un secreto TOTP pendiente de confirmar.")
    if not _totp_valid(user["totp_pending_secret"], code):
        raise WebUserError("El código TOTP es incorrecto o ha caducado.")
    db.execute(
        "UPDATE web_users SET totp_secret = ?, totp_pending_secret = NULL, totp_enabled = 1 "
        "WHERE id = ?",
        (user["totp_pending_secret"], user_id),
    )
    # Al activar el 2FA se revocan las sesiones abiertas antes de tenerlo:
    # una cookie de refresh robada deja de servir sin pasar el segundo factor.
    refresh_tokens.refresh_store.revoke_user_sessions(user_id)


def disable_totp(user_id: int, code: str) -> None:
    """Desactiva el 2FA. Requiere el código actual como confirmación."""
    user = _get_raw(user_id)
    if user is None:
        raise WebUserError("El usuario no existe.")
    if not user.get("totp_enabled"):
        raise WebUserError("El 2FA ya está desactivado para este usuario.")
    if not _totp_valid(user["totp_secret"], code):
        raise WebUserError("El código TOTP es incorrecto o ha caducado.")
    db.execute("UPDATE web_users SET totp_secret = NULL, totp_enabled = 0 WHERE id = ?",
               (user_id,))


def verify_totp_code(user_id: int, code: str | None) -> bool:
    """Valida el código TOTP de un usuario (para el login de segundo paso)."""
    if not code:
        return False
    user = _get_raw(user_id)
    if user is None or not user.get("totp_enabled") or not user.get("totp_secret"):
        return False
    return _totp_valid(user["totp_secret"], code.strip())


def _totp_valid(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:  # noqa: BLE001
        return False