"""Tests de la lógica de la copia fuera del sitio (sin red)."""

from pathlib import Path


def test_rel_key_con_prefijo(db, tmp_path, monkeypatch):
    import core.config as cfg
    from backup import offsite

    base = tmp_path / "backups"
    (base / "nexo").mkdir(parents=True)
    file = base / "nexo" / "x_1.dump.enc"
    file.write_bytes(b".enc")

    monkeypatch.setenv("OFFSITE_PREFIX", "backups/vm1")
    monkeypatch.setenv("OFFSITE_ENABLED", "")
    cfg._settings = None
    assert offsite._rel_key("backups/vm1", file, base) == "backups/vm1/nexo/x_1.dump.enc"
    assert offsite._rel_key("", file, base) == "nexo/x_1.dump.enc"


def test_deshabilitado_no_subirna_nada(db, monkeypatch):
    import core.config as cfg
    from backup import offsite

    monkeypatch.setenv("OFFSITE_ENABLED", "")
    cfg._settings = None
    summary = offsite.sync_new_backups(notify=False)
    assert summary == {"enabled": False, "uploaded": 0, "skipped": 0, "deleted": 0, "errors": []}
    cfg._settings = None


def test_retencion_borra_solo_los_mas_viejos(db, monkeypatch):
    import core.config as cfg
    from backup import offsite

    class FakeClient:
        def __init__(self):
            self.deleted = []

        def delete_object(self, Bucket, Key):
            self.deleted.append(Key)

    monkeypatch.setenv("OFFSITE_KEEP_COUNT", "2")
    cfg._settings = None
    settings_obj = cfg.settings()
    fake = FakeClient()
    keys = [
        "backups/proy-a_20260101.dump.enc",
        "backups/proy-a_20260102.dump.enc",
        "backups/proy-a_20260103.dump.enc",
        "backups/proy-a_20260104.dump.enc",
    ]
    deleted = offsite._apply_retention(fake, settings_obj, keys)
    assert deleted == 2
    assert fake.deleted == [
        "backups/proy-a_20260101.dump.enc",
        "backups/proy-a_20260102.dump.enc",
    ]
    assert offsite._apply_retention(fake, settings_obj, keys[:2]) == 0
    cfg._settings = None


def test_retencion_por_proyecto_no_mezcla_slugs(db, monkeypatch):
    """Regresión: la retención no se aplica de forma global-alfabética, que
    podía borrar los respaldos recientes de un proyecto en favor de otro."""
    import core.config as cfg
    from backup import offsite

    class FakeClient:
        def __init__(self):
            self.deleted = []

        def delete_object(self, Bucket, Key):
            self.deleted.append(Key)

    monkeypatch.setenv("OFFSITE_KEEP_COUNT", "2")
    cfg._settings = None
    settings_obj = cfg.settings()
    fake = FakeClient()
    keys = [
        "backups/proy-a/alfa_20260101.dump.enc",
        "backups/proy-a/alfa_20260102.dump.enc",
        "backups/proy-a/alfa_20260103.dump.enc",
        "backups/proy-b/beta_20260101.dump.enc",
        "backups/proy-b/beta_20260102.dump.enc",
        "backups/proy-b/beta_20260103.dump.enc",
    ]
    deleted = offsite._apply_retention(fake, settings_obj, keys)
    assert deleted == 2
    assert fake.deleted == [
        "backups/proy-a/alfa_20260101.dump.enc",
        "backups/proy-b/beta_20260101.dump.enc",
    ]
    cfg._settings = None


def test_report_errors_notifica_a_admins(db, monkeypatch):
    """Regresión: el fallo de la copia off-site debe avisar a los admins
    (async sin await dejaba la alerta en una corutina que nunca se ejecutaba)."""
    from backup import offsite
    from notify import telegram as notify_mod

    sent: list[str] = []

    async def fake_notify(text):
        sent.append(text)

    monkeypatch.setattr(notify_mod, "notify_admins", fake_notify)
    summary = {"errors": ["no se pudo listar el bucket: boom"]}
    offsite._report_errors(summary, notify=True)
    assert len(sent) == 1
    assert "Falló la copia fuera del sitio" in sent[0]

    offsite._report_errors(summary, notify=False)
    assert len(sent) == 1


def test_prefix_vacio_no_desactiva_la_retencion(db, monkeypatch):
    """C5: aunque OFFSET_PREFIX llegue vacío, la retención sigue lista objetos."""
    import core.config as cfg
    from backup import offsite

    monkeypatch.setenv("OFFSITE_PREFIX", "")
    cfg._settings = None
    try:
        assert cfg.settings().offsite_prefix == "backups"
        assert offsite._prefix() == "backups"
    finally:
        cfg._settings = None