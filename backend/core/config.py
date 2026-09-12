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

        # Mini-WAF por IP (A5): corta ráfagas anómalas hacia /api/*.
        self.throttle_max_requests: int = self._int_env("THROTTLE_MAX_REQUESTS", 120)
        self.throttle_window_seconds: int = self._int_env("THROTTLE_WINDOW_SECONDS", 60)
        self.throttle_block_seconds: int = self._int_env("THROTTLE_BLOCK_SECONDS", 120)

        self.web_admin_username: str = os.getenv("WEB_ADMIN_USERNAME", "admin")
        self.web_admin_password: str = os.getenv("WEB_ADMIN_PASSWORD", "")

        self.session_secret: str = self._required("SESSION_SECRET")

        self.db_path: Path = Path(os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "backups.db")))
        self.backup_dir: Path = Path(os.getenv("BACKUP_DIR", str(PROJECT_ROOT / "data" / "backups")))

        self.backup_keep_count: int = self._int_env("BACKUP_KEEP_COUNT", 10)
        self.backup_timeout_seconds: int = self._int_env("BACKUP_TIMEOUT_SECONDS", 600)
        self.backup_min_free_mb: int = self._int_env("BACKUP_MIN_FREE_MB", 1024)
        self.backup_cooldown_seconds: int = self._int_env("BACKUP_COOLDOWN_SECONDS", 30)
        # Retención de tablas de log (purga semanal automática).
        self.audit_retention_days: int = self._int_env("AUDIT_RETENTION_DAYS", 365)
        self.history_retention_days: int = self._int_env("HISTORY_RETENTION_DAYS", 365)

        # Self-backup de la propia base del panel (SQLite cifrado + Telegram).
        self.self_backup_dir: Path = Path(os.getenv("SELF_BACKUP_DIR", str(self.backup_dir / "self")))
        self.self_backup_keep: int = self._int_env("SELF_BACKUP_KEEP_COUNT", 10)
        self.self_backup_time: str = os.getenv("SELF_BACKUP_TIME", "03:00")
        self.self_backup_tz: str = os.getenv("SELF_BACKUP_TZ", "UTC")
        self.self_backup_telegram: bool = os.getenv("SELF_BACKUP_TELEGRAM", "").strip().lower() in ("1", "true", "yes", "on")

        self.web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
        self.web_port: int = self._int_env("WEB_PORT", 8080)

        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()

        # Resumen diario de salud por Telegram.
        self.daily_summary_enabled: bool = os.getenv("DAILY_SUMMARY_ENABLED", "on").strip().lower() in ("1", "true", "yes", "on")
        self.daily_summary_time: str = os.getenv("DAILY_SUMMARY_TIME", "08:00")
        self.daily_summary_tz: str = os.getenv("DAILY_SUMMARY_TZ", "UTC")

        # Copia fuera del sitio (S3 / R2 / B2 / MinIO). Requiere OFFSITE_ENABLED=on.
        self.offsite_enabled: bool = os.getenv("OFFSITE_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")
        self.offsite_endpoint: str = os.getenv("OFFSITE_ENDPOINT", "").strip()
        self.offsite_region: str = os.getenv("OFFSITE_REGION", "auto").strip()
        self.offsite_access_key: str = os.getenv("OFFSITE_ACCESS_KEY", "")
        self.offsite_secret_key: str = os.getenv("OFFSITE_SECRET_KEY", "")
        self.offsite_bucket: str = os.getenv("OFFSITE_BUCKET", "").strip()
        self.offsite_prefix: str = os.getenv("OFFSITE_PREFIX", "backups").strip() or "backups"
        self.offsite_keep_count: int = self._int_env("OFFSITE_KEEP_COUNT", 30)

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