"""Tests de purga por retención y de la dirección del cliente (XFF)."""

from datetime import datetime, timedelta

from services import audit, backup_history


def _insert_old(db, table, days=400):
    old = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    if table == "audit_log":
        db.execute(
            f"INSERT INTO {table} (accion, resultado, timestamp) VALUES ('t','ok',?)", (old,)
        )
        db.execute("INSERT INTO audit_log (accion, resultado) VALUES ('reciente','ok')")
    else:
        acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
        pid = db.execute(
            "INSERT INTO projects (slug, nombre, account_id, connection_encrypted, project_ref) "
            "VALUES ('p1','P',?, 'conn', 'ref')",
            (acc,),
        )
        db.execute(
            f"INSERT INTO {table} (project_id, resultado, fecha) VALUES (?, 'ok', ?)", (pid, old)
        )
        db.execute(f"INSERT INTO {table} (project_id, resultado) VALUES (?, 'ok')", (pid,))


def test_purge_borra_solo_lo_viejo(db):
    _insert_old(db, "audit_log")
    assert audit.purge_old(365) == 1
    assert db.fetch_one("SELECT COUNT(*) c FROM audit_log WHERE accion='reciente'")["c"] == 1


def test_purge_history_borra_solo_lo_viejo(db):
    _insert_old(db, "backup_history")
    assert backup_history.purge_old(365) == 1
    assert db.fetch_one("SELECT COUNT(*) c FROM backup_history WHERE resultado='ok' AND detalle IS NULL")["c"] >= 0


def test_audit_listado_paginado(db):
    for i in range(5):
        db.execute("INSERT INTO audit_log (accion, resultado) VALUES (?, 'ok')", (f"a{i}",))
    rows = audit.list_audit(limit=2, offset=2)
    assert len(rows) == 2
    assert rows[0]["accion"] == "a2"


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers
        self.client = None


def test_client_address_usa_ultimo_xff():
    from api.rate_limit import _client_address

    assert _client_address(_FakeRequest({"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})) == "5.6.7.8"
    assert _client_address(_FakeRequest({"X-Forwarded-For": "203.0.113.7"})) == "203.0.113.7"
    assert _client_address(_FakeRequest({})) == "unknown"