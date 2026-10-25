"""Tests para la aplicación de backup_options a pg_dump."""

from __future__ import annotations

import subprocess
from pathlib import Path

from backup import runner


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_dump_command_appends_no_owner_and_no_privileges(monkeypatch, tmp_path):
    """pg_dump debe recibir --no-owner y --no-privileges cuando están activados."""
    monkeypatch.setattr(runner, "_pg_dump_binary", lambda: "pg_dump")
    dest = tmp_path / "test.dump"

    args, env = runner._dump_command(
        "postgresql://user:pass@host:5432/dbname",
        dest,
        {"no_owner": True, "no_privileges": True},
    )

    assert "--no-owner" in args
    assert "--no-privileges" in args
    assert args[0] == "pg_dump"
    assert "--format=custom" in args
    assert "--compress=9" in args
    assert "--file" in args
    assert str(dest) in args


def test_dump_command_only_no_privileges(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_pg_dump_binary", lambda: "pg_dump")
    dest = tmp_path / "test.dump"

    args, _env = runner._dump_command(
        "postgresql://user:pass@host:5432/dbname",
        dest,
        {"no_owner": False, "no_privileges": True},
    )

    assert "--no-owner" not in args
    assert "--no-privileges" in args


def test_dump_command_only_no_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_pg_dump_binary", lambda: "pg_dump")
    dest = tmp_path / "test.dump"

    args, _env = runner._dump_command(
        "postgresql://user:pass@host:5432/dbname",
        dest,
        {"no_owner": True},
    )

    assert "--no-owner" in args
    assert "--no-privileges" not in args


def test_dump_command_ignores_unknown_and_none(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_pg_dump_binary", lambda: "pg_dump")
    dest = tmp_path / "test.dump"

    args, _env = runner._dump_command(
        "postgresql://user:pass@host:5432/dbname",
        dest,
        None,
    )
    assert "--no-owner" not in args
    assert "--no-privileges" not in args

    args2, _env2 = runner._dump_command(
        "postgresql://user:pass@host:5432/dbname",
        dest,
        {},
    )
    assert "--no-owner" not in args2
    assert "--no-privileges" not in args2

    args3, _env3 = runner._dump_command(
        "postgresql://user:pass@host:5432/dbname",
        dest,
        {"no_owner": True, "unknown_flag": True},
    )
    assert "--no-owner" in args3
    assert "--no-privileges" not in args3


def test_normalize_dump_flags():
    assert runner._normalize_dump_flags(None) == {}
    assert runner._normalize_dump_flags({}) == {}
    assert runner._normalize_dump_flags({"no_owner": True, "no_privileges": False}) == {
        "no_owner": True,
        "no_privileges": False,
    }
    assert runner._normalize_dump_flags({"no_owner": 1, "no_privileges": 0}) == {
        "no_owner": True,
        "no_privileges": False,
    }
    assert runner._normalize_dump_flags({"extra": True}) == {}
