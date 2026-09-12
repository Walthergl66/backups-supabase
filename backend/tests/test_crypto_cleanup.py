"""Tests de cifrado en reposo y barrido de claros."""

from pathlib import Path

from backup import cleanup
from core import crypto


def test_encrypt_decrypt_roundtrip(db):
    token = crypto.encrypt("postgresql://user:pass@host/db")
    assert token != "postgresql://user:pass@host/db"
    assert crypto.decrypt(token) == "postgresql://user:pass@host/db"


def test_decrypt_clave_incorrecta(db, tmp_path, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    import core.config as cfg
    cfg._settings = None

    token = crypto.encrypt("secreto")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    cfg._settings = None
    import pytest

    with pytest.raises(ValueError):
        crypto.decrypt(token)
    cfg._settings = None


def test_encrypt_file_crea_cifrado_sin_claro_legible(db, tmp_path):
    plain = tmp_path / "db.dump"
    plain.write_bytes(b"SELECT * FROM secretos;")
    enc = tmp_path / "db.dump.enc"
    crypto.encrypt_file(plain, enc)
    assert enc.exists()
    assert "secretos" not in enc.read_text(errors="ignore")
    assert crypto.decrypt_file_bytes(enc) == b"SELECT * FROM secretos;"


def test_barrido_borra_claro_y_conserva_enc(db, tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    import core.config as cfg
    cfg._settings = None

    (tmp_path / "backups" / "nexo").mkdir(parents=True)
    plain = tmp_path / "backups" / "nexo" / "x_20260101.dump"
    enc = tmp_path / "backups" / "nexo" / "x_20260101.dump.enc"
    orphan = tmp_path / "backups" / "nexo" / "y_junk.sql"
    plain.write_bytes(b"claro")
    enc.write_bytes(b"cifrado")
    orphan.write_bytes(b"claro")

    removed = cleanup.sweep_plaintext_backups()
    assert str(plain) in removed
    assert str(orphan) in removed
    assert enc.exists()  # el .enc nunca se toca
    cfg._settings = None