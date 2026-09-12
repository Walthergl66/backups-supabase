"""Configuración de los tests: base de datos y directorios en /tmp aislados.

Los servicios leen la configuración (settings()) de variable de entorno en
cada uso; el fixture `db` les apunta a un SQLite temporal nuevo por test.
"""

from __future__ import annotations

import os

os.environ.setdefault("BOT_TOKEN", "0000000000:TESTTOKEN")
os.environ.setdefault("ENCRYPTION_KEY", "P0plo0y-XXXXXXXX_TBtQIB0zXJmn1DZBgprYJmGMw=")
os.environ.setdefault("BACKUP_ENCRYPTION_KEY", "aZXt3kxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx=")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

import pytest  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Resetea settings y apunta DB/BACKUP a un directorio temporal nuevo."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("SELF_BACKUP_DIR", str(tmp_path / "self"))
    monkeypatch.setenv("SELF_BACKUP_TELEGRAM", "")

    import core.config as cfg
    from core import db as db_mod

    cfg._settings = None
    db_mod.init_db()
    yield db_mod
    cfg._settings = None