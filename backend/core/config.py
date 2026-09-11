"""Configuración central del sistema.

Carga las variables de entorno desde un archivo `.env` (raíz del proyecto)
y las expone de forma tipada. Todas las credenciales viven aquí y nunca
hardcodeadas en el código.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings:
    def __init__(self, env_file: Path | None = None) -> None:
        env_file = env_file or DEFAULT_ENV_FILE
        if env_file.exists():
            load_dotenv(env_file)

        self.package_dir = PROJECT_ROOT

        self.bot_token: str = self._required("BOT_TOKEN")

        self.encryption_key: str = self._required("ENCRYPTION_KEY")

        self.backup_encryption_key: str = self._required("BACKUP_ENCRYPTION_KEY")

        self.cors_allow_origins: list[str] = [
            o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()
        ] or ["http://localhost:8080", "http://127.0.0.1:8080"]

        self.web_docs_enabled: bool = os.getenv("WEB_DOCS_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")

        try:
            self.pbkdf2_iterations: int = int(os.getenv("PBKDF2_ITERATIONS", "600000"))
        except ValueError:
            self.pbkdf2_iterations = 600_000

        # Token de acceso (JWT) corto + refresh token en cookie HttpOnly (M6).
        self.jwt_ttl_seconds: int = self._int_env("JWT_TTL_MINUTES", 60) * 60
        self.refresh_ttl_seconds: int = self._int_env("REFRESH_TTL_DAYS", 7) * 24 * 3600

        self.web_admin_username: str = os.getenv("WEB_ADMIN_USERNAME", "admin")
        self.web_admin_password: str = os.getenv("WEB_ADMIN_PASSWORD", "")

        self.session_secret: str = self._required("SESSION_SECRET")
        self.csrf_secret: str = self._required("CSRF_SECRET")

        self.db_path: Path = Path(os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "backups.db")))
        self.backup_dir: Path = Path(os.getenv("BACKUP_DIR", str(PROJECT_ROOT / "data" / "backups")))

        self.backup_keep_count: int = self._int_env("BACKUP_KEEP_COUNT", 10)
        self.backup_timeout_seconds: int = self._int_env("BACKUP_TIMEOUT_SECONDS", 600)

        self.web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
        self.web_port: int = self._int_env("WEB_PORT", 8080)

    @staticmethod
    def _required(name: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            raise RuntimeError(
                f"Falta la variable de entorno obligatoria {name!r}. "
                "Revisa el archivo .env (usa .env.example como plantilla)."
            )
        return value

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, default))
        except ValueError:
            return default


def get_settings(env_file: Path | None = None) -> Settings:
    return Settings(env_file)


_settings: Settings | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings