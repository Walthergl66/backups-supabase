"""Cifrado en reposo de credenciales (PAT, cadenas de conexión).

Usa Fernet con una clave maestra que vive SOLO en el .env, nunca en la
base de datos ni en la interfaz web.
"""

from __future__ import annotations

from pathlib import Path
import struct

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

_FILE_MAGIC = b"SBENC2\n"
_FILE_CHUNK_SIZE = 1024 * 1024


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
    """Cifra por bloques para mantener acotado el uso de memoria.

    El formato legado Fernet se sigue aceptando al descifrar. El archivo
    original NO se toca; quien llame debe borrarlo del disco.
    """
    cipher = _backup_fernet()
    try:
        with plaintext_path.open("rb") as source, output_path.open("wb") as target:
            target.write(_FILE_MAGIC)
            while chunk := source.read(_FILE_CHUNK_SIZE):
                token = cipher.encrypt(chunk)
                target.write(struct.pack(">I", len(token)))
                target.write(token)
            target.write(struct.pack(">I", 0))
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def decrypt_file_bytes(token_path: Path) -> bytes:
    """Descifra un archivo de backup y devuelve su contenido en claro
    (en memoria, sin tocar el disco)."""
    try:
        token = token_path.read_bytes()
        if not token.startswith(_FILE_MAGIC):
            return _backup_fernet().decrypt(token)  # formato Fernet anterior
        cipher = _backup_fernet()
        result = bytearray()
        offset = len(_FILE_MAGIC)
        while offset + 4 <= len(token):
            size = struct.unpack(">I", token[offset:offset + 4])[0]
            offset += 4
            if size == 0:
                if offset != len(token):
                    raise InvalidToken
                return bytes(result)
            if offset + size > len(token):
                raise InvalidToken
            result.extend(cipher.decrypt(token[offset:offset + size]))
            offset += size
        raise InvalidToken
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
