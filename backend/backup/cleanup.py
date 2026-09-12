"""Barrido de archivos de backup en claro (`*.dump`/`*.sql`).

Durante la ejecución de un backup conviven brevemente archivos SIN cifrar
(el `.dump` recién generado y su `.sql`). Suelen borrarse al cifrarlos, pero
si el proceso muere a mitad (o falla el cifrado) pueden quedar huérfanos en
`BACKUP_DIR`. Este barrido se lanza al arrancar:
  - si el claro tiene su pareja `.enc`: seguro borrarlo (existe la copia cifrada);
  - si no tiene pareja: se borra igualmente (viola la garantía "sin claro en
    disco") y se avisa a los admins por Telegram con la lista de lo eliminado.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)


def sweep_plaintext_backups() -> list[str]:
    """Elimina restos `.dump`/`.sql` sin cifrar y devuelve las rutas borradas."""
    base: Path = settings().backup_dir
    if not base.is_dir():
        return []

    removed: list[str] = []
    for plain in sorted(base.rglob("*.dump")):
        if plain.is_file():
            _unlink(plain)
            removed.append(str(plain))
    for plain in sorted(base.rglob("*.sql")):
        if plain.is_file():
            _unlink(plain)
            removed.append(str(plain))
    # También barre temporales propios (sqlite backup en curso quedó a medias).
    for tmp in sorted(base.rglob("*.tmp")):
        if tmp.is_file():
            _unlink(tmp)
            removed.append(str(tmp))

    if removed:
        logger.warning("Barrido al arranque: %d archivo(s) en claro eliminados.", len(removed))
    return removed


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("No se pudo borrar resto en claro %s: %s", path, exc)