"""Traducción de errores de PostgreSQL a mensajes amigables.

Centraliza el mapeo del stderr de `psql`/`pg_dump` para que tanto el motor de
backup como la API y el bot hablen el mismo idioma. No depende de Supabase:
cualquier PostgreSQL devuelve estos errores.
"""

from __future__ import annotations


def friendly_db_error(stderr: str) -> str:
    """Traduce el stderr de psql/pg_dump a un mensaje amigable para el usuario."""
    low = (stderr or "").lower()
    if "password authentication failed" in low or "no password supplied" in low:
        return "la contraseña o el usuario de la base de datos son incorrectos"
    if 'role "' in low and "does not exist" in low:
        return "el usuario de la base de datos no existe"
    if "does not exist" in low or "not found" in low:
        return "el nombre de la base de datos no coincide con el proyecto"
    if "could not translate host name" in low or "name or service not known" in low or "getaddrinfo" in low:
        return "no se pudo resolver el servidor (revisa la URL o tu conexión a internet)"
    if "timed out" in low or "timeout" in low or "time out" in low:
        return "la conexión tardó demasiado y se canceló (probablemente tu red bloquea este servidor)"
    if "connection refused" in low:
        return "el servidor rechazó la conexión (puede estar apagado o bloqueado)"
    if "no pg_hba.conf entry" in low:
        return "el servidor no permite conexiones desde esta IP (revisa pg_hba.conf o el firewall)"
    if "too many connections" in low:
        return "el servidor alcanzó su límite de conexiones"
    if "server version mismatch" in low or "aborting because of server version mismatch" in low:
        return "la versión de pg_dump es menor que la del servidor (actualiza postgresql-client)"
    if "ssl" in low:
        return "falló el cifrado SSL de la conexión"
    return "no se pudo conectar con el servidor de base de datos"
