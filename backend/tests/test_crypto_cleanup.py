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

def test_run_backup_usa_verify_dump_y_completa(db, tmp_path, monkeypatch):
    """Regresión: run_backup debe llamar a verify_dump (no _verify_dump)."""
    import subprocess
    from backup import runner
    from services import projects as projects_srv

    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("BACKUP_KEEP_COUNT", "5")
    import core.config as cfg
    cfg._settings = None

    dest_dir = tmp_path / "backups" / "nexo"
    dest_dir.mkdir(parents=True)

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if "--list" in args:  # verify_dump (pg_restore --list)
            return subprocess.CompletedProcess(args, 0, stdout="Item 1\nItem 2\n", stderr="")
        if args[0] == "pg_restore":  # conversión a SQL
            out = Path(args[args.index("--file") + 1])
            out.write_bytes(b"SELECT 1;")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        # pg_dump
        dest = Path(args[args.index("--file") + 1])
        dest.write_bytes(b"%s" % bytes(64))
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    # Asegurarse de que pg_restore/pg_dump "existen"
    monkeypatch.setattr(runner, "_pg_dump_binary", lambda: "pg_dump")
    monkeypatch.setattr(runner, "_pg_restore_binary", lambda: "pg_restore")

    result = runner.run_backup(
        {"id": 1, "slug": "nexo", "connection_plain": "postgresql://x:y@h/db"}
    )

    assert result.ok is True
    assert any("pg_dump" in c and "--list" not in c for c in calls)
    assert any("--list" in c for c in calls)  # se llamó a verify_dump
    cfg._settings = None
