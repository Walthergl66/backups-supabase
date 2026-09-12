"""Capa de acceso a la base de datos.

SQLite se usa con conexiones cortas por operación (no se comparte entre
hilos), WAL y foreign keys activadas. Toda la lógica de lectura/escritura
pasa por `services/`, que es la única capa que importa SQLite; esto deja
desacoplada la persistencia para una futura migración a Postgres.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from core.config import settings


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings().db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    """Crea los directorios y ejecuta el esquema solo si la base aún no existe."""
    db_path: Path = settings().db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists() or db_path.stat().st_size == 0:
        schema = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
        with connect() as conn:
            conn.executescript(schema.read_text(encoding="utf-8"))
    _migrate()


def _migrate() -> None:
    """Migraciones incrementales para bases de datos existentes."""
    statements = [
        "ALTER TABLE users ADD COLUMN supabase_pat_encrypted TEXT",
        "ALTER TABLE web_users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE web_users ADD COLUMN locked_until TEXT",
        "ALTER TABLE projects ADD COLUMN schedule TEXT",
        "ALTER TABLE projects ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
    ]
    with connect() as conn:
        for statement in statements:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                pass  # La columna ya existe


def fetch_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchone()


def fetch_all(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Ejecuta una escritura y devuelve el id de la última fila insertada (o -1)."""
    with connect() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid if cur.lastrowid is not None else -1


def execute_many(sql: str, seq_of_params: Iterable[Iterable[Any]]) -> None:
    with connect() as conn:
        conn.executemany(sql, seq_of_params)