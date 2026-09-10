"""Cuentas de Supabase (PAT encriptado en reposo)."""

from __future__ import annotations

from core import db, crypto


class AccountError(Exception):
    pass


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
        "pat_masked": crypto.mask(crypto.decrypt(row["pat_encrypted"])),
    }


def create_account(nombre: str, pat: str) -> int:
    nombre = nombre.strip()
    pat = pat.strip()
    if not nombre or not pat:
        raise AccountError("Nombre y Personal Access Token son obligatorios.")
    return db.execute(
        "INSERT INTO accounts (nombre, pat_encrypted) VALUES (?, ?)",
        (nombre, crypto.encrypt(pat)),
    )


def get_account(account_id: int) -> dict | None:
    return _row_to_dict(db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,)))


def list_accounts() -> list[dict]:
    return [
        _row_to_dict(r)
        for r in db.fetch_all("SELECT * FROM accounts ORDER BY nombre")
    ]


def update_account(account_id: int, nombre: str | None = None, pat: str | None = None) -> None:
    current = db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if current is None:
        raise AccountError("La cuenta no existe.")
    new_nombre = (nombre or "").strip() or current["nombre"]
    if pat is not None and pat.strip():
        db.execute(
            "UPDATE accounts SET nombre = ?, pat_encrypted = ? WHERE id = ?",
            (new_nombre, crypto.encrypt(pat.strip()), account_id),
        )
    else:
        db.execute("UPDATE accounts SET nombre = ? WHERE id = ?", (new_nombre, account_id))


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
    return crypto.decrypt(row["pat_encrypted"])