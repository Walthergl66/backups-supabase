"""Proyectos respaldados (PostgreSQL genérico o Supabase).

Cada proyecto representa una base PostgreSQL concreta. El proveedor solo
decide las capacidades extra (importación y estado cloud), nunca el motor de
backup: `pg_dump` trabaja siempre contra la cadena de conexión cifrada.
"""

from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import parse_qsl, urlparse

from apscheduler.triggers.cron import CronTrigger

from core import crypto, db

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
<<<<<<< HEAD
PROVIDERS = ("supabase", "postgres")
_ALLOWED_BACKUP_OPTIONS = ("no_owner", "no_privileges")
=======
MAX_SLUG_LENGTH = 63

# Marcador que devuelve Supabase cuando la connection string no trae la
# contraseña real. Si se guardara literal, los backups fallarían con
# "password" = "[YOUR-PASSWORD]".
_PASSWORD_MARKER = "[YOUR-PASSWORD]"

# Parámetros libpq que sí se admiten en el query de la connection string.
# Todo lo demás (options, host/port/dbname por parámetro...) se rechaza:
# esos podrían redirigir la conexión a otro sitio o alterar la ejecución.
_LIBPQ_ALLOWED_PARAMS = frozenset({
    "sslmode", "sslrootcert", "sslcert", "sslkey",
    "connect_timeout", "application_name", "target_session_attrs",
    "gssencmode", "channel_binding", "keepalives", "keepalives_idle",
})


def _require_real_connection(connection: str) -> None:
    if _PASSWORD_MARKER in connection:
        raise ProjectError(
            "La cadena de conexión llega con el marcador [YOUR-PASSWORD]: "
            "falta la contraseña real del proyecto."
        )
    parsed = urlparse(connection)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ProjectError(
            "La cadena de conexión debe empezar por postgresql://"
        )
    if not parsed.hostname:
        raise ProjectError(
            "La cadena de conexión debe incluir el host "
            "(postgresql://usuario:clave@host:puerto/base)."
        )
    if parsed.query:
        known = frozenset(k for k, _ in parse_qsl(parsed.query))
        forbidden = sorted(known - _LIBPQ_ALLOWED_PARAMS)
        if forbidden:
            raise ProjectError(
                "La cadena de conexión incluye parámetros libpq no permitidos "
                f"({', '.join(forbidden)}) y se rechaza por seguridad."
            )
>>>>>>> origin/main


def slugify(text: str) -> str:
    """Normaliza un texto a un slug ascii en minúsculas (a-z, 0-9, guiones)."""
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


class ProjectError(Exception):
    pass


def _validate_provider(provider: str | None) -> str:
    value = (provider or "").strip().lower()
    if value not in PROVIDERS:
        raise ProjectError("Proveedor inválido. Usa 'supabase' o 'postgres'.")
    return value


def _validate_connection(connection: str) -> None:
    """Exige una URI de PostgreSQL válida.

    Se limita a URI (no conninfo con `host=...`) porque el ejecutor extrae
    las credenciales para pasarlas por entorno y no por `argv`.
    """
    if not connection.startswith(("postgresql://", "postgres://")):
        raise ProjectError(
            "La cadena de conexión debe ser una URI que empiece por "
            "'postgresql://' o 'postgres://'."
        )


def _validate_schedule(schedule: str | None) -> str | None:
    """Valida un cron de 5 campos. Devuelve la expresión normalizada o None."""
    expr = (schedule or "").strip()
    if not expr:
        return None
    if len(expr.split()) != 5:
        raise ProjectError("El cron debe tener 5 campos: minuto hora día mes día-semana (ej. '30 3 * * *').")
    try:
        CronTrigger.from_crontab(expr)
    except Exception as exc:  # noqa: BLE001 - cualquier formato inválido
        raise ProjectError(f"Expresión cron inválida: {exc}") from exc
    return expr


def _normalize_backup_options(value, provider: str) -> dict:
    """Normaliza las opciones de pg_dump a un dict JSON-serializable."""
    if value is None or value == "":
        options = {"no_owner": True, "no_privileges": True} if provider == "postgres" else {}
    elif isinstance(value, str):
        try:
            options = json.loads(value)
        except ValueError as exc:
            raise ProjectError("Las opciones de backup no son un JSON válido.") from exc
    elif isinstance(value, dict):
        options = value
    else:
        raise ProjectError("Las opciones de backup deben ser un objeto JSON.")

    if not isinstance(options, dict):
        raise ProjectError("Las opciones de backup deben ser un objeto JSON.")
    unknown = set(options) - set(_ALLOWED_BACKUP_OPTIONS)
    if unknown:
        raise ProjectError(
            f"Opción de backup desconocida: {', '.join(sorted(unknown))}. "
            f"Permitidas: {', '.join(_ALLOWED_BACKUP_OPTIONS)}."
        )
    return {key: bool(options.get(key)) for key in _ALLOWED_BACKUP_OPTIONS if key in options}


def _read_backup_options(raw) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _dict(row, include_secret: bool = False) -> dict | None:
    if row is None:
        return None
    connection_plain = crypto.decrypt(row["connection_encrypted"])
    data = {
        "id": row["id"],
        "slug": row["slug"],
        "nombre": row["nombre"],
        "provider": row["provider"] if "provider" in row.keys() else "supabase",
        "account_id": row["account_id"],
        "account_nombre": row["account_nombre"] if "account_nombre" in row.keys() else None,
        "project_ref": row["project_ref"] or "",
        "activo": bool(row["activo"]),
        "created_at": row["created_at"],
        "schedule": row["schedule"] if "schedule" in row.keys() else None,
        "backup_options": _read_backup_options(
            row["backup_options"] if "backup_options" in row.keys() else None
        ),
        # Rellenado por consultas con JOIN cuando está disponible
        "connection_masked": crypto.mask(connection_plain)
        if not include_secret
        else connection_plain,
        "ultimo_backup": row["ultimo_backup"] if "ultimo_backup" in row.keys() else None,
        "tamaño_archivo": row["ultimo_tamano"] if "ultimo_tamano" in row.keys() else None,
    }
    if include_secret:
        data["connection_plain"] = connection_plain
    return data


def _base_select(last_backup_join: bool = True) -> str:
    join = (
        """
        LEFT JOIN (
            SELECT project_id, MAX(fecha) AS ultimo_backup,
                   (SELECT tamaño_archivo FROM backup_history bh2
                    WHERE bh2.project_id = bh.project_id AND bh2.resultado = 'ok'
                    ORDER BY bh2.fecha DESC, bh2.id DESC LIMIT 1) AS ultimo_tamano
            FROM backup_history bh
            WHERE resultado = 'ok'
            GROUP BY project_id
        ) bh ON bh.project_id = p.id
        """
        if last_backup_join
        else ""
    )
    return (
        "SELECT p.*, a.nombre AS account_nombre, bh.ultimo_backup, bh.ultimo_tamano "
        f"FROM projects p JOIN accounts a ON a.id = p.account_id {join}"
    )


<<<<<<< HEAD
def _resolve_account(account_id: int | None, provider: str) -> int:
    if account_id:
        account = db.fetch_one("SELECT id, provider FROM accounts WHERE id = ?", (account_id,))
        if account is None:
            raise ProjectError("La cuenta asociada no existe.")
        account_provider = account["provider"] if "provider" in account.keys() else "supabase"
        if account_provider != provider:
            raise ProjectError(
                f"La cuenta seleccionada es de tipo '{account_provider}' y el proyecto "
                f"es de tipo '{provider}'. Elige una cuenta compatible."
            )
        return account_id

    # Sin cuenta explícita: solo los proyectos genéricos usan el grupo por defecto.
    if provider != "postgres":
        raise ProjectError("La cuenta es obligatoria para proyectos Supabase.")
    from services import accounts as accounts_srv

    return accounts_srv.ensure_default_group()


def create_project(
    slug: str,
    nombre: str,
    account_id: int | None,
    connection: str,
    project_ref: str = "",
    schedule: str | None = None,
    provider: str | None = None,
    backup_options=None,
) -> int:
    slug = slug.strip()
    nombre = (nombre or "").strip()
    connection = (connection or "").strip()
    project_ref = (project_ref or "").strip()
    explicit_provider = (provider or "").strip().lower()
    provider = _validate_provider(explicit_provider or ("supabase" if project_ref else "postgres"))
=======
def is_supabase_project(project: dict) -> bool:
    """True si el proyecto tiene ref de Supabase (usa Management API).

    Una ref vacía significa BD PostgreSQL genérica: backup, psql y scheduler
    funcionan igual, pero no hay Management API (import, estado Supabase).
    """
    return bool((project.get("project_ref") or "").strip())


def create_project(slug: str, nombre: str, account_id: int, connection: str, project_ref: str | None = None,
                   schedule: str | None = None) -> int:
    slug = slug.strip()
    nombre = (nombre or "").strip()
    connection = connection.strip()
    project_ref = (project_ref or "").strip()
>>>>>>> origin/main
    schedule = _validate_schedule(schedule)
    if not slug:
        slug = slugify(nombre)
    if not _SLUG_RE.match(slug):
        raise ProjectError(
            "Slug inválido. Usa solo minúsculas, números, guiones o guiones bajos "
            "(debe empezar por letra o número)."
        )
<<<<<<< HEAD
    if not nombre or not connection:
        raise ProjectError("Nombre y cadena de conexión son obligatorios.")
    _validate_connection(connection)
    if provider == "supabase" and not project_ref:
        raise ProjectError("La referencia del proyecto (project_ref) es obligatoria para Supabase.")
=======
    if len(slug) > MAX_SLUG_LENGTH:
        raise ProjectError(f"El slug no puede superar los {MAX_SLUG_LENGTH} caracteres.")
    if not nombre or not connection:
        raise ProjectError("Nombre y cadena de conexión son obligatorios.")
    # project_ref vacío = BD PostgreSQL genérica (sin Management API de Supabase).
    _require_real_connection(connection)
>>>>>>> origin/main
    existing = db.fetch_one("SELECT id FROM projects WHERE slug = ?", (slug,))
    if existing is not None:
        raise ProjectError(f"Ya existe un proyecto con el slug '{slug}'.")

    account_id = _resolve_account(account_id, provider)
    options = _normalize_backup_options(backup_options, provider)
    return db.execute(
        """
        INSERT INTO projects (slug, nombre, provider, account_id, connection_encrypted,
                              project_ref, backup_options, schedule)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug,
            nombre,
            provider,
            account_id,
            crypto.encrypt(connection),
            project_ref,
            json.dumps(options) if options else None,
            schedule,
        ),
    )


def get_project(project_id: int, include_secret: bool = False) -> dict | None:
    row = db.fetch_one(
        f"{_base_select()} WHERE p.id = ?",
        (project_id,),
    )
    return _dict(row, include_secret=include_secret)


def get_by_slug(slug: str) -> dict | None:
    row = db.fetch_one(
        f"{_base_select()} WHERE p.slug = ?",
        (slug,),
    )
    return _dict(row)


def list_projects(only_active: bool = True, provider: str | None = None) -> list[dict]:
    sql = _base_select()
    where: list[str] = []
    params: list = []
    if only_active:
        where.append("p.activo = 1")
    if provider:
        where.append("p.provider = ?")
        params.append(_validate_provider(provider))
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.slug"
    return [_dict(r) for r in db.fetch_all(sql, params)]


def update_project(
    project_id: int,
    slug: str | None = None,
    nombre: str | None = None,
    account_id: int | None = None,
    connection: str | None = None,
    project_ref: str | None = None,
    activo: bool | None = None,
    schedule: str | None = None,
    provider: str | None = None,
    backup_options=None,
) -> None:
    current = db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if current is None:
        raise ProjectError("El proyecto no existe.")

    new_provider = _validate_provider(
        provider if provider is not None else current["provider"]
        if "provider" in current.keys() else "supabase"
    )
    new_slug = (slug or "").strip() or current["slug"]
    if new_slug != current["slug"]:
        if not _SLUG_RE.match(new_slug):
            raise ProjectError("Slug inválido.")
        if len(new_slug) > MAX_SLUG_LENGTH:
            raise ProjectError(f"El slug no puede superar los {MAX_SLUG_LENGTH} caracteres.")
        clash = db.fetch_one("SELECT id FROM projects WHERE slug = ? AND id != ?", (new_slug, project_id))
        if clash is not None:
            raise ProjectError(f"Ya existe un proyecto con el slug '{new_slug}'.")
<<<<<<< HEAD

    new_connection_encrypted = current["connection_encrypted"]
    if connection and connection.strip():
        _validate_connection(connection.strip())
        new_connection_encrypted = crypto.encrypt(connection.strip())

    new_project_ref = (
        (project_ref or "").strip()
        if project_ref is not None
        else (current["project_ref"] or "")
    )
    if new_provider == "supabase" and not new_project_ref:
        raise ProjectError("La referencia del proyecto (project_ref) es obligatoria para Supabase.")
    if new_provider == "postgres":
        # Los proyectos genéricos no tienen referencia de Supabase.
        new_project_ref = ""

    current_provider = (
        current["provider"] if "provider" in current.keys() else "supabase"
    )
    new_account_id = current["account_id"]
    if account_id is not None:
        new_account_id = _resolve_account(account_id, new_provider)
    elif new_provider != current_provider:
        # Al cambiar de proveedor sin indicar cuenta, se resuelve una
        # compatible (grupo por defecto para PostgreSQL directo).
        new_account_id = _resolve_account(None, new_provider)

    if backup_options is None:
        new_backup_options = (
            current["backup_options"] if "backup_options" in current.keys() else None
        )
    else:
        options = _normalize_backup_options(backup_options, new_provider)
        new_backup_options = json.dumps(options) if options else None

    new_schedule = (
        _validate_schedule(schedule) if schedule is not None else current["schedule"]
    )
=======
    if connection and connection.strip():
        _require_real_connection(connection.strip())
    new_connection = crypto.encrypt(connection.strip()) if connection and connection.strip() else current["connection_encrypted"]
    new_schedule = _validate_schedule(schedule) if schedule is not None else current["schedule"]
    # project_ref None = sin cambio; "" = convertir a PostgreSQL genérica.
    new_ref = current["project_ref"] if project_ref is None else project_ref.strip()
>>>>>>> origin/main
    db.execute(
        """
        UPDATE projects
        SET slug = ?, nombre = ?, provider = ?, account_id = ?, connection_encrypted = ?,
            project_ref = ?, backup_options = ?, activo = ?, schedule = ?
        WHERE id = ?
        """,
        (
            new_slug,
            (nombre or "").strip() or current["nombre"],
<<<<<<< HEAD
            new_provider,
            new_account_id,
            new_connection_encrypted,
            new_project_ref,
            new_backup_options,
=======
            account_id or current["account_id"],
            new_connection,
            new_ref,
>>>>>>> origin/main
            1 if activo is None else int(activo),
            new_schedule,
            project_id,
        ),
    )


def delete_project(project_id: int) -> None:
    """Eliminación lógica: desactiva el proyecto y libera el slug.

    El historial de backups y el audit_log se conservan intactos.
    """
    current = db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if current is None:
        raise ProjectError("El proyecto no existe.")
    archived_slug = f"(eliminado)-{current['id']}-{current['slug']}"
    db.execute(
        "UPDATE projects SET activo = 0, archived = 1, slug = ? WHERE id = ?",
        (archived_slug, project_id),
    )


def restore_project(project_id: int, slug: str | None = None) -> None:
    """Reactivación desde la vista de proyectos eliminados."""
    current = db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if current is None:
        raise ProjectError("El proyecto no existe.")
    candidate = (slug or "").strip() or re.sub(r"^\(eliminado\)-\d+-", "", current["slug"] or "")
    if not _SLUG_RE.match(candidate):
        raise ProjectError("Slug inválido para restaurar.")
    clash = db.fetch_one("SELECT id FROM projects WHERE slug = ? AND id != ?", (candidate, project_id))
    if clash is not None:
        raise ProjectError(f"El slug '{candidate}' ya está en uso por otro proyecto.")
    db.execute(
        "UPDATE projects SET activo = 1, archived = 0, slug = ? WHERE id = ?",
        (candidate, project_id),
    )


def last_backup_ok(project_id: int) -> str | None:
    row = db.fetch_one(
        "SELECT fecha FROM backup_history WHERE project_id = ? AND resultado = 'ok' ORDER BY fecha DESC LIMIT 1",
        (project_id,),
    )
    return row["fecha"] if row else None


def project_extra_status(project_id: int) -> dict:
    """Datos de estado no sensibles para el panel web."""
    history = db.fetch_all(
        "SELECT resultado, COUNT(*) AS c FROM backup_history WHERE project_id = ? GROUP BY resultado",
        (project_id,),
    )
    stats = {"backups_ok": 0, "backups_error": 0}
    for row in history:
        stats[f"backups_{row['resultado']}"] = row["c"]
    return stats
