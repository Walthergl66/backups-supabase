"""Cifrado en reposo de credenciales (PAT, cadenas de conexión).

Usa Fernet con una clave maestra que vive SOLO en el .env, nunca en la
base de datos ni en la interfaz web.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings


def _fernet() -> Fernet:
    return Fernet(settings().encryption_key.encode("utf-8"))


def _backup_fernet() -> Fernet:
    return Fernet(settings().backup_encryption_key.encode("utf-8"))


def encrypt(plaintext: str) -> str:
    """Cifra un valor y lo devuelve como texto base64. No debe invocarse
    sobre campos no sensibles."""
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Descifra un valor previamente cifrado con `encrypt`."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError(
            "No se pudo descifrar el valor. La clave maestra de ENCRYPTION_KEY "
            "¿ha cambiado o es incorrecta?"
        ) from exc


def encrypt_file(plaintext_path: Path, output_path: Path) -> None:
    """Cifra un archivo de backup al completo y lo escribe en `output_path`.
    El archivo original NO se toca; quien llame debe borrarlo del disco."""
    token = _backup_fernet().encrypt(plaintext_path.read_bytes())
    output_path.write_bytes(token)


def decrypt_file_bytes(token_path: Path) -> bytes:
    """Descifra un archivo de backup y devuelve su contenido en claro
    (en memoria, sin tocar el disco)."""
    try:
        return _backup_fernet().decrypt(token_path.read_bytes())
    except (InvalidToken, ValueError) as exc:
        raise ValueError(
            "No se pudo descifrar el backup. ¿La clave BACKUP_ENCRYPTION_KEY "
            "ha cambiado?"
        ) from exc


def mask(value: str) -> str:
    """Máscara segura para mostrar en la interfaz (solo últimos 4 caracteres)."""
    if not value:
        return "(vacío)"
    return "••••" + value[-4:]