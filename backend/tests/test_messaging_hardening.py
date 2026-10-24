"""Tests de las correcciones de mensajería y red (C6-C9)."""

import asyncio


def test_send_message_trocea_mensajes_largos(db):
    """C6: los mensajes de más de 4096 caracteres se envían por trozos sin
    cortar líneas a la mitad."""
    from notify import telegram

    class FakeBot:
        def __init__(self):
            self.sent: list[str] = []

        async def send_message(self, chat_id, text, disable_web_page_preview):
            self.sent.append(text)

    bot = FakeBot()
    text = "\n".join(f"línea {i}" for i in range(800))
    asyncio.run(telegram.send_message(bot, 1, text))
    assert len(bot.sent) > 1
    assert all(len(t) <= telegram._MAX_TEXT for t in bot.sent)
    assert "\n".join(bot.sent) == text


def test_send_message_cabe_en_uno(db):
    from notify import telegram

    class FakeBot:
        def __init__(self):
            self.sent: list[str] = []

        async def send_message(self, chat_id, text, disable_web_page_preview):
            self.sent.append(text)

    bot = FakeBot()
    asyncio.run(telegram.send_message(bot, 1, "hola"))
    assert bot.sent == ["hola"]


def test_validate_pat_error_red_no_filtra_detalles():
    """C7: un error de red/TLS al validar el PAT no revela IPs ni detalles."""
    import httpx

    from services import supabase_api as api
    from unittest.mock import patch

    with patch.object(
        api.httpx,
        "get",
        side_effect=httpx.ConnectError("TLS handshake to 203.0.113.7:443 failed"),
    ):
        ok, msg = api.validate_pat("sbp_pat")
    assert ok is False
    assert "203.0.113.7" not in msg
    assert "TLS" not in msg
    assert "conectar" in msg.lower()


def test_validate_pat_401_mensaje_amigable():
    from unittest.mock import Mock, patch

    from services import supabase_api as api

    resp = Mock()
    resp.status_code = 401
    with patch.object(api.httpx, "get", return_value=resp):
        ok, msg = api.validate_pat("sbp_pat")
    assert ok is False
    assert "token" in msg.lower()


def test_run_self_backup_borra_tmp_si_falla_el_cifrado(db, tmp_path, monkeypatch):
    """C4: aunque el cifrado del self-backup falle, no queda un .tmp en claro."""
    import pytest

    from backup import self_backup

    dest = tmp_path / "self"
    dest.mkdir()
    monkeypatch.setenv("SELF_BACKUP_DIR", str(dest))

    import core.config as cfg
    cfg._settings = None
    try:

        def boom(_plain, _enc):
            raise RuntimeError("fallo forzado del cifrado")

        monkeypatch.setattr(self_backup.crypto_mod, "encrypt_file", boom)
        with pytest.raises(RuntimeError):
            self_backup.run_self_backup()
        assert list(dest.glob("panel_*.tmp")) == []
        assert list(dest.glob("panel_*.sqlite.enc")) == []
    finally:
        cfg._settings = None


def test_send_latest_no_nombra_enc_para_contenido_en_claro(db, tmp_path, monkeypatch):
    """C9: el self-backup se envía descifrado; el nombre no debe llevar .enc."""
    from backup import self_backup

    dest = tmp_path / "self"
    dest.mkdir()
    (dest / "panel_20260101_000000.sqlite.enc").write_bytes(b"\x00" * 64)
    monkeypatch.setenv("SELF_BACKUP_DIR", str(dest))

    import core.config as cfg
    cfg._settings = None
    try:
        monkeypatch.setattr(
            self_backup.crypto_mod, "decrypt_file_bytes", lambda _p: b"CONTENIDO-EN-CLARO"
        )
        sent = {}

        async def fake_doc(filename, data, caption=""):
            sent["filename"] = filename
            sent["data"] = data
            sent["caption"] = caption

        async def fake_admins(_text):
            return None

        monkeypatch.setattr("notify.telegram.notify_admins_document", fake_doc)
        monkeypatch.setattr("notify.telegram.notify_admins", fake_admins)
        asyncio.run(self_backup.send_latest_to_telegram())

        assert sent.get("filename") == "panel_20260101_000000.sqlite"
        assert ".enc" not in sent["filename"]
        assert sent["data"] == b"CONTENIDO-EN-CLARO"
    finally:
        cfg._settings = None