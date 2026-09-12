"""Resumen diario de salud del sistema para los admins de Telegram.

Recorre los proyectos activos, mira su último backup (OK y error) y genera
un mensaje de un vistazo. Si algún proyecto lleva más de `STALE_HOURS` sin
un backup correcto, lo marca para que se atienda. Se envían solo resúmenes
con contenido (no se manda si no hay proyectos activos).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from services import backup_history, projects

STALE_HOURS = 26
_TIME_FMT = "%Y-%m-%d %H:%M:%S"


def build_daily_summary() -> str:
    active = projects.list_projects(only_active=True)
    if not active:
        return ""

    now = datetime.now()
    cutoff = now - timedelta(hours=STALE_HOURS)
    lines: list[str] = ["📊 Resumen diario de backups", ""]
    stale_count = 0

    for p in active:
        last = backup_history.recent(p["id"], limit=5)
        ok = next((r for r in last if r["resultado"] == "ok"), None)
        err = next((r for r in last if r["resultado"] == "error"), None)

        if ok is None:
            lines.append(f"• <b>{p['slug']}</b> — ⚠️ sin backups correctos todavía")
            stale_count += 1
            continue

        ok_when = _parse(ok["fecha"])
        if ok_when is None or ok_when < cutoff:
            lines.append(
                f"• <b>{p['slug']}</b> — ⚠️ sin backup OK desde {ok['fecha']} (> {STALE_HOURS} h)"
            )
            stale_count += 1
        else:
            size = f" · {ok['tamaño_archivo']:,.0f} MB" if ok.get("tamaño_archivo") else ""
            lines.append(f"• {p['slug']} — backup OK {ok['fecha']}{size}")

        if err is not None and (ok is None or _parse(err["fecha"]) > _parse(ok["fecha"])):
            lines.append(f"  └─ ⚠️ último intento falló: {err.get('detalle') or 'error'} ({err['fecha']})")

    lines.insert(1, f"<b>{now.strftime('%Y-%m-%d %H:%M UTC')}</b> · {len(active)} proyectos activos · {stale_count} con riesgo")

    if stale_count:
        lines.append("")
        lines.append("🔴 Hay proyectos que necesitan un backup. Revisa el panel o usa /backup.")

    return "\n".join(lines)


def send_daily_summary() -> None:
    from notify import telegram as notify_mod

    text = build_daily_summary()
    if not text:
        return
    notify_mod.notify_admins(text)


def _parse(value: str) -> datetime | None:
    try:
        return datetime.strptime((value or "").strip(), _TIME_FMT)
    except ValueError:
        return None