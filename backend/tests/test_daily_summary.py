"""Tests del resumen diario por Telegram."""

from datetime import datetime, timedelta

from core import crypto
from notify.daily_summary import build_daily_summary


def _seed_project(db, slug, last_ok=None, last_err=None):
    acc = db.execute("INSERT INTO accounts (nombre, pat_encrypted) VALUES ('A','x')")
    pid = db.execute(
        "INSERT INTO projects (slug, nombre, account_id, connection_encrypted, project_ref) "
        "VALUES (?, 'P', ?, ?, 'ref')",
        (slug, acc, crypto.encrypt("postgresql://u:p@h/d")),
    )
    if last_ok:
        db.execute(
            "INSERT INTO backup_history (project_id, resultado, ruta_archivo, fecha) "
            "VALUES (?, 'ok', 'x.dump.enc', ?)",
            (pid, last_ok.strftime("%Y-%m-%d %H:%M:%S")),
        )
    if last_err:
        db.execute(
            "INSERT INTO backup_history (project_id, resultado, fecha) VALUES (?, 'error', ?)",
            (pid, last_err.strftime("%Y-%m-%d %H:%M:%S")),
        )
    return pid


def test_sin_proyectos_no_genera_resumen(db):
    assert build_daily_summary() == ""


def test_proyecto_sano_marca_ok(db):
    _seed_project(db, "sano", last_ok=datetime.now())
    text = build_daily_summary()
    assert "sano" in text
    assert "backup OK" in text
    assert "con riesgo" not in text or "0 con riesgo" in text


def test_proyecto_sin_backup_nunca_marca_alerta(db):
    _seed_project(db, "dormido")
    text = build_daily_summary()
    assert "dormido" in text
    assert "sin backups correctos" in text
    assert "necesitan un backup" in text


def test_proyecto_stale_marca_alerta(db):
    _seed_project(db, "antiguo", last_ok=datetime.now() - timedelta(hours=40))
    text = build_daily_summary()
    assert "antiguo" in text
    assert "sin backup OK desde" in text


def test_error_posterior_al_ok_se_avisa(db):
    now = datetime.now()
    _seed_project(db, "dudoso", last_ok=now - timedelta(hours=2), last_err=now - timedelta(hours=1))
    text = build_daily_summary()
    assert "último intento falló" in text