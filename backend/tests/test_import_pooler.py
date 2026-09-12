"""Tests del pooler automático en importación (session mode + inyección de contraseña)."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from services import supabase_api as api


# --- _pick_pooler ---

def test_pick_prefiere_session():
    poolers = [
        {"database_type": "PRIMARY", "pool_mode": "transaction", "connection_string": "t://x"},
        {"database_type": "PRIMARY", "pool_mode": "session", "connection_string": "s://x"},
    ]
    assert api._pick_pooler(poolers, "session").get("connection_string") == "s://x"

def test_pick_fallback_a_transaction():
    poolers = [
        {"database_type": "PRIMARY", "pool_mode": "transaction", "connection_string": "t://x"},
    ]
    assert api._pick_pooler(poolers, "session").get("connection_string") == "t://x"

def test_pick_vacio():
    assert api._pick_pooler([], "session") is None


# --- _inject_password ---

PLACEHOLDER = "postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres"


def test_inyecta_password_placeholder():
    out = api._inject_password(PLACEHOLDER, "s3cret p@ss")
    assert "postgres.xxx:s3cret%20p%40ss@aws" in out
    assert "[YOUR-PASSWORD]" not in out

def test_inyecta_password_sin_placeholder():
    url = "postgresql://postgres.xxx@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    out = api._inject_password(url, "mi_pass")
    assert "mi_pass@aws" in out

def test_none_deja_igual():
    assert api._inject_password(PLACEHOLDER, None) == PLACEHOLDER

def test_password_vacia_deja_igual():
    assert api._inject_password(PLACEHOLDER, "") == PLACEHOLDER

def test_password_especiales():
    out = api._inject_password(PLACEHOLDER, "a&b=c#d")
    assert "a%26b%3Dc%23d@" in out


# --- get_connection_string con mock ---

SESSION_POOLERS = [
    {"database_type": "PRIMARY", "pool_mode": "transaction", "connection_string": "pg://t"},
    {"database_type": "PRIMARY", "pool_mode": "session", "connection_string": "pg://s:[YOUR-PASSWORD]@h:5432/db"},
]

def test_get_cs_session_y_password():
    resp = type("R", (), {"status_code": 200, "json": lambda self: SESSION_POOLERS})()
    with patch.object(api.httpx, "get", return_value=resp):
        out = api.get_connection_string("pat", "ref", mode="session", password="x")
    assert out == "pg://s:x@h:5432/db"

def test_get_cs_sin_password():
    resp = type("R", (), {"status_code": 200, "json": lambda self: SESSION_POOLERS})()
    with patch.object(api.httpx, "get", return_value=resp):
        out = api.get_connection_string("pat", "ref", mode="session", password=None)
    assert "[YOUR-PASSWORD]" in out

def test_get_cs_http_error():
    import httpx
    with patch.object(api.httpx, "get", side_effect=httpx.HTTPError("fail")):
        assert api.get_connection_string("pat", "ref") is None

def test_get_cs_status_500():
    resp = type("R", (), {"status_code": 500, "json": lambda self: []})()
    with patch.object(api.httpx, "get", return_value=resp):
        assert api.get_connection_string("pat", "ref") is None


# --- test_connection ---

def test_test_connection_sin_psql(monkeypatch):
    monkeypatch.setattr(api.shutil, "which", lambda _: None)
    ok, detail = api.test_connection("pg://x:pass@h/db")
    assert ok is True
    assert "omitida" in detail
