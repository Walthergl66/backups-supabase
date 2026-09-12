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