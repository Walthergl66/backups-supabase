"""Cuentas o grupos de conexión (credenciales cifradas en reposo).

Una cuenta puede ser de Supabase (con Personal Access Token para importar
proyectos) o un grupo genérico de PostgreSQL directo (sin PAT). El modelo
sigue usando `accounts` como agrupador para no romper los datos existentes.
"""

from __future__ import annotations

from core import crypto, db

PROVIDERS = ("supabase", "postgres")


class AccountError(Exception):
    pass


def _validate_provider(provider: str | None) -> str:
    value = (provider or "supabase").strip().lower()
    if value not in PROVIDERS:
        raise AccountError("Proveedor inválido. Usa 'supabase' o 'postgres'.")
    return value


def _plain_pat(row) -> str:
    return crypto.decrypt(row["pat_encrypted"]) if row["pat_encrypted"] else ""


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    pat = _plain_pat(row)
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "provider": row["provider"] if "provider" in row.keys() else "supabase",
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
        "pat_masked": crypto.mask(pat) if pat else "(sin PAT)",
        "has_pat": bool(pat),
    }


def _row_to_dict_plain(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "provider": row["provider"] if "provider" in row.keys() else "supabase",
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
        "pat": _plain_pat(row),
    }


def create_account(nombre: str, pat: str, provider: str = "supabase") -> int:
    provider = _validate_provider(provider)
    nombre = nombre.strip()
    pat = (pat or "").strip()
    if not nombre:
        raise AccountError("El nombre de la cuenta es obligatorio.")
    if provider == "supabase" and not pat:
        raise AccountError("El Personal Access Token es obligatorio para cuentas Supabase.")

    if provider == "supabase":
        # Reutiliza la cuenta activa que ya tenga este mismo PAT para no
        # duplicar registros al reimportar (p. ej. tras eliminar un proyecto).
        for row in db.fetch_all("SELECT * FROM accounts WHERE activo = 1"):
            data = _row_to_dict_plain(row)
            if data and data["pat"] == pat:
                if data["nombre"] != nombre or data["provider"] != provider:
                    db.execute(
                        "UPDATE accounts SET nombre = ?, provider = ? WHERE id = ?",
                        (nombre, provider, data["id"]),
                    )
                return data["id"]
    else:
        # Los grupos genéricos se deduplican por nombre y proveedor.
        existing = db.fetch_one(
            "SELECT id FROM accounts WHERE activo = 1 AND provider = ? AND nombre = ?",
            (provider, nombre),
        )
        if existing is not None:
            return existing["id"]

    return db.execute(
        "INSERT INTO accounts (nombre, provider, pat_encrypted) VALUES (?, ?, ?)",
        (nombre, provider, crypto.encrypt(pat)),
    )


def get_account(account_id: int) -> dict | None:
    return _row_to_dict(db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,)))


def list_accounts() -> list[dict]:
    return [
        _row_to_dict(r)
        for r in db.fetch_all("SELECT * FROM accounts ORDER BY provider, nombre")
    ]


def update_account(
    account_id: int,
    nombre: str | None = None,
    pat: str | None = None,
    provider: str | None = None,
) -> None:
    current = db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if current is None:
        raise AccountError("La cuenta no existe.")

    new_provider = _validate_provider(provider if provider is not None else current["provider"])
    new_nombre = (nombre or "").strip() or current["nombre"]
    new_pat_encrypted = (
        crypto.encrypt(pat.strip())
        if pat is not None and pat.strip()
        else current["pat_encrypted"]
    )
    plain_pat = crypto.decrypt(new_pat_encrypted) if new_pat_encrypted else ""
    if new_provider == "supabase" and not plain_pat:
        raise AccountError("El Personal Access Token es obligatorio para cuentas Supabase.")

    db.execute(
        "UPDATE accounts SET nombre = ?, provider = ?, pat_encrypted = ? WHERE id = ?",
        (new_nombre, new_provider, new_pat_encrypted, account_id),
    )


def delete_account(account_id: int) -> None:
    count = db.fetch_one(
        "SELECT COUNT(*) AS c FROM projects WHERE account_id = ?", (account_id,)
    )
    if count and count["c"] > 0:
        raise AccountError(
            "No se puede eliminar: la cuenta tiene proyectos asociados. "
            "Elimina primero (o reasigna) sus proyectos."
        )
    db.execute("UPDATE accounts SET activo = 0 WHERE id = ?", (account_id,))
    db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


def get_plaintext_pat(account_id: int) -> str:
    row = db.fetch_one("SELECT pat_encrypted FROM accounts WHERE id = ?", (account_id,))
    if row is None:
        raise AccountError("La cuenta no existe.")
    return _plain_pat(row)


def has_pat(account_id: int) -> bool:
    """True si la cuenta tiene un PAT utilizable (solo Supabase)."""
    return bool(get_plaintext_pat(account_id))


def ensure_default_group() -> int:
    """Devuelve el id del grupo de conexiones PostgreSQL directas.

    Lo crea si no existe. Es el destino por defecto de los proyectos que no
    pertenecen a un proveedor cloud.
    """
    existing = db.fetch_one(
        "SELECT id FROM accounts WHERE provider = 'postgres' ORDER BY id LIMIT 1"
    )
    if existing is not None:
        return existing["id"]
    return create_account(db.DEFAULT_GROUP_NAME, "", provider="postgres")
