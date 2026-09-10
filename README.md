# Bot de Backups y Monitoreo de Supabase

Sistema multiplataforma (Linux, macOS, Windows) para respaldar bases de datos de
Supabase **bajo demanda** desde Telegram y administrar todas las conexiones desde
una interfaz web, sin tocar código ni archivos de configuración.

## Componentes

| Componente | Qué hace |
|---|---|
| Bot de Telegram | `/proyectos`, `/backup <slug>`, `/status <slug>`, `/historial <slug>` |
| Interfaz web | CRUD de cuentas, proyectos, usuarios y permisos, con roles y log de auditoría |
| Motor de backups | `pg_dump -Fc` en Python puro, rotación de los últimos N backups por proyecto |

La arquitectura es de **un solo proceso**: el bot de Telegram y la web de
FastAPI comparten contenedor y base SQLite. Es suficiente para uso personal o de
un equipo pequeño, y evita coordinar varios servicios. La acceso a datos está
desacoplada en `services/` por si en el futuro se quisiera migrar a Postgres y
separar los procesos.

## Arquitectura

```
.
├── main.py                 # levanta la web + el bot en un solo proceso
├── db/schema.sql           # esquema SQLite
├── core/                   # config, conexión a BD, cifrado, sesiones/CSRF
├── services/               # capa de datos desacoplada (persistencia única)
├── backup/                 # ejecutor de pg_dump + comprobaciones de estado
├── bot/                    # comandos de Telegram y validaciones
├── notify/                 # canal de notificación (Telegram)
├── admin_web/              # FastAPI + plantillas (login, roles, CRUD)
├── Dockerfile              # python:3.12-slim + postgresql-client
└── docker-compose.yml      # un solo servicio, restart: unless-stopped
```

## Requisitos previos

- Docker con Docker Compose (principal).
- Un bot de Telegram creado con [@BotFather](https://t.me/BotFather) (necesitarás su token).
- Los `project_ref` y las cadenas de conexión de tus proyectos de Supabase
  (Dashboard → Project Settings → Database).
- Un [Personal Access Token](https://supabase.com/dashboard/account/tokens) de Supabase.

## Instalación (método principal: Docker)

**1. Crea el archivo de entorno.**

```bash
cp .env.example .env
```

**2. Completa `.env`.**

```bash
BOT_TOKEN=123456:ABC...          # token de @BotFather
ENCRYPTION_KEY=...               # genera una: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=un-password-fuerte
SESSION_SECRET=...               # python -c "import secrets; print(secrets.token_urlsafe(48))"
CSRF_SECRET=...                  # idem
```

El resto de variables ya traen valores por defecto razonables
(`8080`, `BACKUP_KEEP_COUNT=10`, etc.).

> **Importante:** `ENCRYPTION_KEY` cifra en reposo los PAT y las cadenas de
> conexión. Si la pierdes o la cambias, no podrás descifrar lo que ya esté
> guardado.

**3. Levanta el sistema.**

```bash
docker compose up -d --build
```

La web queda disponible en `http://localhost:8080`.

**4. Primera configuración (imprescindible):**

- Entra con `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` y **cambia la
  contraseña** desde *Usuarios Web*.
- **Importa desde *Importar proyectos***: pega el PAT de Supabase, selecciona
  los proyectos y en el mismo paso registra tu **usuario de Telegram**
  (nombre + `chat_id`). Al confirmar se crea la cuenta, los proyectos y el
  usuario con permisos sobre los proyectos importados.
  - ¿Cómo saber tu `chat_id`? Envía cualquier mensaje a tu bot y revisa los
    logs: se registra al intentar usarlo.
  - Si prefieres, puedes crear cuentas y proyectos manualmente (CRUD en
    *Cuentas* / *Proyectos*) y registrar usuarios desde *Usuarios Telegram*.
    El rol `admin` de Telegram tiene permisos totales; los roles `usuario`
    se configuran permiso a permiso por proyecto.

Los datos (SQLite y backups) se guardan en `./data`, que es un volumen Docker:
sobreviven a `docker compose down`.

**Dónde están los backups.** Dentro del contenedor se almacenan en `/data/backups/<slug>/`.
En el host, en `./data/backups/<slug>/`. Rotación por defecto: **10 backups por proyecto**.

## Uso del bot de Telegram

| Comando | Descripción |
|---|---|
| `/proyectos` | Lista los proyectos activos con su último backup |
| `/backup <slug>` | Dispara un backup bajo demanda (formato `pg_dump -Fc`) |
| `/status <slug>` | Comprueba conexión a la base y estado vía Management API |
| `/historial <slug>` | Últimos backups del proyecto |

Toda acción queda registrada en `audit_log` y en el historial
(`backup_history`). Un chat no autorizado recibe siempre una respuesta genérica.

## Seguridad

- Credenciales cifradas en reposo con Fernet (clave maestra solo en `.env`).
- La interfaz nunca muestra credenciales completas (solo los últimos 4 caracteres).
- Contraseñas web con PBKDF2-SHA256 (salt por usuario).
- Sesiones con cookie `HttpOnly` + protección CSRF por formulario.
- Roles web: `admin` (CRUD completo) y `viewer` (solo lectura).
- El slug de cada proyecto se valida contra la whitelist de la base antes de
  usarse en cualquier llamada de sistema.

## Gestión del sistema

```bash
docker compose logs -f          # logs del proceso (web + bot)
docker compose down             # detener (los datos permanecen en ./data)
docker compose up -d            # volver a arrancar
```

## Alternativa nativa (opcional, sin Docker)

El proyecto también corre directo con Python 3.10+ y `pg_dump`/`psql`
(`postgresql-client`, `libpq` o equivalente) instalados en el sistema.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# completa .env, creando los directorios si hace falta (DB_PATH/BACKUP_DIR)
python main.py
```

Si no defines `DB_PATH`/`BACKUP_DIR`, se crean bajo `./data` automáticamente.
La web queda en `http://localhost:8080`. Para que se mantenga activo sin Docker,
usa el mecanismo de tu sistema:

### Linux (systemd)

`/etc/systemd/system/supabase-backups.service`:

```ini
[Unit]
Description=Supabase Backups bot + web
After=network-online.target

[Service]
WorkingDirectory=/ruta/al/proyecto
ExecStart=/ruta/al/proyecto/.venv/bin/python main.py
EnvironmentFile=/ruta/al/proyecto/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now supabase-backups
```

> Nota: asignar `EnvironmentFile` hace que `.env` no se recargue vía
> python-dotenv al `working dir`; el fallback del loader no hace daño. Si quieres,
> omite `EnvironmentFile`, ya que el código carga `.env` automáticamente.

### macOS (launchd)

`~/Library/LaunchAgents/com.supabase.backups.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.supabase.backups</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ruta/al/proyecto/.venv/bin/python</string>
    <string>/ruta/al/proyecto/main.py</string>
  </array>
  <key>WorkingDirectory</key><string>/ruta/al/proyecto</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.supabase.backups.plist
```

### Windows (Programador de tareas)

Crea `run.bat`:

```bat
cd /d C:\ruta\al\proyecto
.venv\Scripts\python.exe main.py
```

En el Programador de tareas: acción "Iniciar un programa" apuntando a
`run.bat`, activar "Ejecutar con los máximos privilegios" y en
*Configuración* marcar "Si la tarea no se completa, reiniciar cada 5 minutos".

## Variables de entorno

| Variable | Descripción |
|---|---|
| `BOT_TOKEN` | Token del bot de Telegram (obligatorio) |
| `ENCRYPTION_KEY` | Clave Fernet para cifrar credenciales (obligatorio) |
| `SESSION_SECRET` / `CSRF_SECRET` | Secretos de sesión / CSRF (obligatorio) |
| `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` | Solo para crear el primer admin si no hay ninguno |
| `DB_PATH` | Ruta del SQLite (default `/data/backups.db` en Docker) |
| `BACKUP_DIR` | Carpeta de backups (default `/data/backups` en Docker) |
| `BACKUP_KEEP_COUNT` | Rotación: backups a conservar por proyecto (default 10) |
| `BACKUP_TIMEOUT_SECONDS` | Timeout de `pg_dump` en segundos (default 600) |
| `WEB_HOST` / `WEB_PORT` | Interfaz web (default `0.0.0.0:8080`) |

## Notas

- Los backups son **solo bajo demanda** (por Telegram). No hay cron/crontab en
  esta versión.
- Las notificaciones son exclusivamente por Telegram: no se ha configurado el
  canal de correo (Resend) a petición del cliente.
- El diseño de `permissions` y `audit_log` deja lista una futura Fase 2 con
  autorregistro de usuarios, límites de uso y filtrado por proyecto.