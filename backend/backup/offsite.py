"""Copia fuera del sitio de los backups `.enc` (S3 / R2 / B2 / MinIO).

Cada archivo cifrado que aparece en `BACKUP_DIR` se sube a un bucket S3
compatible usando boto3. Después de subir se aplica retención remota:
se borran los objetos más antiguos por encima de `OFFSITE_KEEP_COUNT`.

Si algo falla, se avisa a los admins de Telegram con el detalle; los
archivos se re-sincronizan en el siguiente arranque o backup con éxito
(los que ya están remotos se saltan).
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config

from core.config import settings

logger = logging.getLogger(__name__)


def _client():
    cfg = settings()
    return boto3.client(
        "s3",
        endpoint_url=cfg.offsite_endpoint,
        region_name=cfg.offsite_region,
        aws_access_key_id=cfg.offsite_access_key,
        aws_secret_access_key=cfg.offsite_secret_key,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def _rel_key(prefix: str, file: Path, base: Path) -> str:
    rel = file.relative_to(base).as_posix()
    if not prefix:
        return rel
    return f"{prefix.rstrip('/')}/{rel}"


def list_remote_keys() -> list[str]:
    """Todos los objetos del bucket bajo el prefijo configurado."""
    cfg = settings()
    if not cfg.offsite_prefix:
        return []
    keys: list[str] = []
    paginator = _client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=cfg.offsite_bucket, Prefix=cfg.offsite_prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def sync_new_backups(notify: bool = True) -> dict:
    """Sube los `.enc` nuevos y aplica retención remota. Devuelve resumen."""
    cfg = settings()
    summary = {"enabled": False, "uploaded": 0, "skipped": 0, "deleted": 0, "errors": []}
    if not cfg.offsite_enabled:
        return summary
    summary["enabled"] = True

    base: Path = cfg.backup_dir
    if not base.is_dir():
        return summary

    try:
        client = _client()
        remote = set(list_remote_keys())
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"no se pudo listar el bucket: {exc}")
        _report_errors(summary, notify)
        return summary

    new_files = [
        p for p in sorted(base.rglob("*.enc"))
        if p.is_file() and _rel_key(cfg.offsite_prefix, p, base) not in remote
    ]
    for file in new_files:
        key = _rel_key(cfg.offsite_prefix, file, base)
        try:
            client.upload_file(str(file), cfg.offsite_bucket, key)
            summary["uploaded"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"{quote(key)}: {exc}")

    if summary["errors"]:
        _report_errors(summary, notify)

    if cfg.offsite_keep_count > 0:
        try:
            summary["deleted"] = _apply_retention(client, cfg, list_remote_keys())
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"retención remota: {exc}")

    if summary["deleted"]:
        logger.info("Copia fuera del sitio: %d subido(s), %d borrado(s) por retención.",
                    summary["uploaded"], summary["deleted"])
    elif summary["uploaded"]:
        logger.info("Copia fuera del sitio: %d archivo(s) subido(s).", summary["uploaded"])
    return summary


def _apply_retention(client, cfg, keys: list[str], bucket: str | None = None) -> int:
    """Borra los objetos más antiguos (por orden alfabético) por encima de keep_count."""
    keep = max(1, cfg.offsite_keep_count)
    bucket = bucket or cfg.offsite_bucket
    if len(keys) <= keep:
        return 0
    ordered = sorted(keys)[: len(keys) - keep]
    if not ordered:
        return 0
    deleted = 0
    for key in ordered:
        client.delete_object(Bucket=bucket, Key=key)
        deleted += 1
    return deleted


def _report_errors(summary: dict, notify: bool) -> None:
    if not notify or not summary["errors"]:
        return
    from notify import telegram as notify_mod
    from core import sanitize

    detail = "\n".join(f"- {sanitize.redact_secrets(e)}" for e in summary["errors"][:10])
    try:
        notify_mod.notify_admins(
            "⚠️ Falló la copia fuera del sitio de los backups:\n" + detail
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo notificar el fallo de la copia off-site: %s", exc)