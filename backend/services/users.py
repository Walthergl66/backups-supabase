"""Usuarios del bot de Telegram y sus permisos sobre proyectos.

El rol 'admin' tiene, de forma implícita, can_backup y can_monitor sobre
todos los proyectos activos. El resto de los roles depende de la tabla
`permissions`.
"""

from __future__ import annotations

from core import db, crypto


class UserError(Exception):
    pass


def user_dict(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "telegram_chat_id": row["telegram_chat_id"],
        "nombre": row["nombre"],
        "rol": row["rol"],
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
    }


def create_user(telegram_chat_id: int, nombre: str, rol: str = "usuario") -> int:
    nombre = (nombre or "").strip()
    rol = rol.strip() if rol.strip() else "usuario"
    if rol not in ("admin", "usuario"):
        raise UserError("Rol inválido (admin | usuario).")
    if db.fetch_one("SELECT id FROM users WHERE telegram_chat_id = ?", (telegram_chat_id,)):
        raise UserError("Ese chat_id ya está registrado.")
    return db.execute(
        "INSERT INTO users (telegram_chat_id, nombre, rol) VALUES (?, ?, ?)",
        (telegram_chat_id, nombre, rol),
    )


def get_user(telegram_chat_id: int) -> dict | None:
    return user_dict(
        db.fetch_one("SELECT * FROM users WHERE telegram_chat_id = ?", (telegram_chat_id,))
    )


def get_user_by_id(user_id: int) -> dict | None:
    return user_dict(db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,)))


def list_users() -> list[dict]:
    return [user_dict(r) for r in db.fetch_all("SELECT * FROM users ORDER BY nombre")]


def list_admin_chat_ids() -> list[int]:
    """Chats de Telegram con rol admin que recibirán alertas de seguridad."""
    return [
        int(r["telegram_chat_id"])
        for r in db.fetch_all(
            "SELECT telegram_chat_id FROM users WHERE rol = 'admin' AND activo = 1"
        )
    ]


def update_user(user_id: int, nombre: str | None = None, rol: str | None = None, activo: bool | None = None) -> None:
    current = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if current is None:
        raise UserError("El usuario no existe.")
    new_rol = (rol or "").strip() or current["rol"]
    if new_rol not in ("admin", "usuario"):
        raise UserError("Rol inválido.")
    db.execute(
        "UPDATE users SET nombre = ?, rol = ?, activo = ? WHERE id = ?",
        ((nombre or "").strip() or current["nombre"], new_rol,
         1 if activo is None else int(activo), user_id),
    )


def delete_user(user_id: int) -> None:
    db.execute("DELETE FROM permissions WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))


def upsert_permission(user_id: int, project_id: int, can_backup: bool, can_monitor: bool) -> None:
    db.execute(
        """
        INSERT INTO permissions (user_id, project_id, can_backup, can_monitor)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, project_id) DO UPDATE SET
            can_backup = excluded.can_backup,
            can_monitor = excluded.can_monitor
        """,
        (user_id, project_id, int(can_backup), int(can_monitor)),
    )


def delete_permission(user_id: int, project_id: int) -> None:
    db.execute(
        "DELETE FROM permissions WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    )


def get_permissions(user_id: int) -> list[dict]:
    return [
        {
            "project_id": r["project_id"],
            "slug": r["slug"],
            "can_backup": bool(r["can_backup"]),
            "can_monitor": bool(r["can_monitor"]),
        }
        for r in db.fetch_all(
            """
            SELECT pr.project_id, p.slug, pr.can_backup, pr.can_monitor
            FROM permissions pr JOIN projects p ON p.id = pr.project_id
            WHERE pr.user_id = ?
            ORDER BY p.slug
            """,
            (user_id,),
        )
    ]


_CAN_PERMISSIONS = frozenset({"can_backup", "can_monitor"})


def can(user_id: int, project_id: int, permission: str) -> bool:
    """Comprueba si el usuario (admin implícito o permiso explícito) puede
    realizar `permission` (can_backup | can_monitor) sobre el proyecto."""
    if permission not in _CAN_PERMISSIONS:
        raise UserError(f"Permiso desconocido: {permission!r}")
    user = db.fetch_one("SELECT rol, activo FROM users WHERE id = ?", (user_id,))
    if user is None or not user["activo"]:
        return False
    if user["rol"] == "admin":
        return True
    row = db.fetch_one(
        f"SELECT {permission} FROM permissions WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    )
    return bool(row and row[permission])


def authorized_chat(telegram_chat_id: int) -> dict | None:
    """Devuelve el usuario si está registrado y activo."""
    return get_user(telegram_chat_id)


def save_pat(telegram_chat_id: int, pat: str) -> None:
    """Guarda el PAT de Supabase del usuario (cifrado)."""
    db.execute(
        "UPDATE users SET supabase_pat_encrypted = ? WHERE telegram_chat_id = ?",
        (crypto.encrypt(pat.strip()), telegram_chat_id),
    )


def get_pat(telegram_chat_id: int) -> str | None:
    """Devuelve el PAT descifrado del usuario, o None si no tiene."""
    row = db.fetch_one(
        "SELECT supabase_pat_encrypted FROM users WHERE telegram_chat_id = ?",
        (telegram_chat_id,),
    )
    if row is None or row["supabase_pat_encrypted"] is None:
        return None
    return crypto.decrypt(row["supabase_pat_encrypted"])


def has_pat(telegram_chat_id: int) -> bool:
    """True si el usuario tiene un PAT registrado."""
    row = db.fetch_one(
        "SELECT supabase_pat_encrypted FROM users WHERE telegram_chat_id = ?",
        (telegram_chat_id,),
    )
    return row is not None and row["supabase_pat_encrypted"] is not None


def find_account_by_chat_id(telegram_chat_id: int) -> dict | None:
    """Busca la cuenta de Supabase asociada al usuario del bot.

    La cuenta se identifica por el nombre 'Telegram: <chat_id>'.
    """
    nombre = f"Telegram: {telegram_chat_id}"
    row = db.fetch_one("SELECT * FROM accounts WHERE nombre = ?", (nombre,))
    if row is None:
        return None
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "activo": bool(row["activo"]),
    }