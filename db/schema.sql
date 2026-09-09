-- Esquema de base de datos (SQLite)
-- Los bloques DROP facilitan regenerar la base durante desarrollo.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS backup_history;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS users;          -- usuarios del bot de Telegram
DROP TABLE IF EXISTS web_users;      -- usuarios de la interfaz web
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS accounts;

-- ------------------------------------------------------------------
-- Cuentas de Supabase (PAT encriptado).
-- ------------------------------------------------------------------
CREATE TABLE accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    pat_encrypted TEXT NOT NULL,        -- Personal Access Token, cifrado (Fernet)
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    activo      INTEGER NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------------
-- Proyectos individuales.
-- ------------------------------------------------------------------
CREATE TABLE projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,            -- identificador corto, usado en los comandos del bot
    nombre        TEXT NOT NULL,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    connection_encrypted TEXT NOT NULL,            -- cadena de conexión a PostgreSQL (pooler), cifrada
    project_ref   TEXT NOT NULL,                   -- referencia para la Management API
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    activo        INTEGER NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------------
-- Usuarios del bot de Telegram.
-- ------------------------------------------------------------------
CREATE TABLE users (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id        INTEGER NOT NULL UNIQUE,
    nombre                  TEXT NOT NULL,
    rol                     TEXT NOT NULL DEFAULT 'usuario',  -- admin | usuario
    supabase_pat_encrypted  TEXT,                             -- PAT de Supabase, cifrado (Fernet)
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    activo                  INTEGER NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------------
-- Permisos por usuario de Telegram y proyecto.
-- Diseñada desde el inicio para una futura Fase 2 con más usuarios.
-- ------------------------------------------------------------------
CREATE TABLE permissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    can_backup  INTEGER NOT NULL DEFAULT 0,
    can_monitor INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, project_id)
);

-- ------------------------------------------------------------------
-- Usuarios de la interfaz web (con roles).
-- ------------------------------------------------------------------
CREATE TABLE web_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,                    -- hash PBKDF2-SHA256
    rol           TEXT NOT NULL DEFAULT 'admin',    -- admin | viewer
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    activo        INTEGER NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------------
-- Historial de backups por proyecto.
-- ------------------------------------------------------------------
CREATE TABLE backup_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    fecha         TEXT NOT NULL DEFAULT (datetime('now')),
    tamaño_archivo REAL,
    resultado     TEXT NOT NULL,                    -- ok | error
    ruta_archivo  TEXT,
    detalle       TEXT
);

-- ------------------------------------------------------------------
-- Log de auditoría de acciones (bot y web).
-- ------------------------------------------------------------------
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,                             -- usuario de Telegram (puede ser NULL)
    web_user_id INTEGER,                             -- usuario web (puede ser NULL)
    project_id  INTEGER,
    accion      TEXT NOT NULL,
    resultado   TEXT NOT NULL,                       -- ok | error
    detalle     TEXT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_backup_history_project
    ON backup_history (project_id, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_permissions_user
    ON permissions (user_id);

CREATE INDEX IF NOT EXISTS idx_permissions_project
    ON permissions (project_id);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp
    ON audit_log (timestamp DESC);