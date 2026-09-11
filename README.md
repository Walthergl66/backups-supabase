# Bot de Backups y Monitoreo de Supabase

Sistema multiplataforma (Linux, macOS, Windows) para respaldar bases de datos de
Supabase **bajo demanda** desde Telegram y administrar todas las conexiones desde
una interfaz **web progresiva (PWA)** adaptable a móvil, sin tocar código ni
archivos de configuración.

## Componentes

| Componente | Qué hace |
|---|---|
| Bot de Telegram | `/proyectos`, `/backup <slug>`, `/status <slug>`, `/historial <slug>` |
| Frontend (SPA + PWA) | Panel React accesible desde el móvil, instalable como app |
| Backend (API REST) | Auth JWT, CRUD de cuentas/proyectos/usuarios/permisos, log de auditoría |
| Motor de backups | `pg_dump -Fc` en Python puro, rotación de los últimos N backups por proyecto |

El backend de FastAPI sirve **solo JSON** sobre una API protegida con tokens JWT
(Bearer). El frontend es una SPA en React servida por nginx, que además proxya
`/api` hacia el backend. El bot de Telegram y la web comparten el mismo proceso
y la misma base SQLite.

## Arquitectura

```
.
├── backend/
│   ├── main.py                 # levanta la API + el bot en un solo proceso
│   ├── db/schema.sql           # esquema SQLite
│   ├── core/                   # config, conexión a BD, cifrado, JWT
│   ├── services/               # capa de datos desacoplada (persistencia única)
│   ├── backup/                 # ejecutor de pg_dump + comprobaciones de estado
│   ├── bot/                    # aplicación del bot: application.py + handlers/ por dominio
│   │   ├── application.py      # wiring de handlers y polling
│   │   └── handlers/           # basics, backup_cmd, status_cmd, register, addbd, misc
│   ├── notify/                 # canal de notificación (Telegram)
│   ├── api/                    # FastAPI: auth JWT + rutas REST en /api
│   ├── .env                    # credenciales (ver backend/.env.example)
│   └── Dockerfile              # python:3.12-slim + postgresql-client
├── frontend/
│   ├── src/                    # React (Vite) + PWA (vite-plugin-pwa)
│   ├── public/icons/           # iconos del manifesto (generados con scripts/generate-icons.mjs)
│   ├── Dockerfile              # build Node -> estáticos servidos con nginx
│   └── nginx.conf              # sirve la SPA y proxya /api -> backend:8080
├── data/                       # SQLite + backups (volumen Docker)
└── docker-compose.yml          # 2 servicios: backend (interno) + frontend (público)
```

## Requisitos previos

- Docker con Docker Compose (principal).
- Un bot de Telegram creado con [@BotFather](https://t.me/BotFather) (necesitarás su token).
- Los `project_ref` y las cadenas de conexión de tus proyectos de Supabase
  (Dashboard → Project Settings → Database).
- Un [Personal Access Token](https://supabase.com/dashboard/account/tokens) de Supabase.

## Instalación (método principal: Docker)

**1. Crea el archivo de entorno del backend.**

```bash
cp backend/.env.example backend/.env
```

**2. Completa `backend/.env`.**

```bash
BOT_TOKEN=123456:ABC...          # token de @BotFather
ENCRYPTION_KEY=...               # genera una: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
BACKUP_ENCRYPTION_KEY=...        # otra distinta, para cifrar los archivos de backup
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=un-password-fuerte
SESSION_SECRET=...               # clave HMAC de los JWT: python -c "import secrets; print(secrets.token_urlsafe(48))"
```

El resto de variables ya traen valores por defecto razonables
(`BACKUP_KEEP_COUNT=10`, `BACKUP_TIMEOUT_SECONDS=600`, etc.).

> **Importante:** `ENCRYPTION_KEY` cifra en reposo los PAT y las cadenas de
> conexión. Si la pierdes o la cambias, no podrás descifrar lo que ya esté
> guardado. `SESSION_SECRET` firma los tokens JWT: si la cambias, las sesiones
> activas se invalidan. `BACKUP_ENCRYPTION_KEY` cifra los archivos de backup
> (`.dump`/`.sql`) en disco; si la cambias, los backups ya cifrados no se
> podrán descifrar.

**3. Levanta el sistema.**

```bash
docker compose up -d --build
```

El panel queda disponible en `http://localhost:8080`.

**4. Primera configuración (imprescindible):**

- Entra con `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` y **cambia la
  contraseña** desde *Usuarios Web*.
- **Importa desde *Importar proyectos***: pega el PAT de Supabase, selecciona
  los proyectos y en el mismo paso registra tu **usuario de Telegram**
  (nombre + `chat_id`). Al confirmar se crea la cuenta, los proyectos y el
  usuario con permisos sobre los proyectos importados.
  - ¿Cómo saber tu `chat_id`? Márcale `/id` al bot en Telegram y te lo responde
    en el propio chat (alternativa a los logs).
  - Si prefieres, puedes crear cuentas y proyectos manualmente (CRUD en
    *Cuentas* / *Proyectos*) y registrar usuarios desde *Usuarios Telegram*.
    El rol `admin` de Telegram tiene permisos totales; los roles `usuario`
    se configuran permiso a permiso por proyecto.

Los datos (SQLite y backups) se guardan en `./data`, que es un volumen Docker:
sobreviven a `docker compose down`.

## Desarrollo del frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 con proxy /api -> localhost:8000
```

Para probar contra un backend local en el puerto 8000:

```bash
cd backend
cp .env.example .env   # completa .env
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python main.py         # inicia API + bot
```

Los iconos del PWA se regeneran con `node scripts/generate-icons.mjs`.

## Uso del bot de Telegram

| Comando | Descripción |
|---|---|
| `/id` | Devuelve tu `chat_id` en el chat (sirve para darte de alta sin revisar logs) |
| `/proyectos` | Lista los proyectos activos con su último backup |
| `/backup <slug>` | Dispara un backup bajo demanda (formato `pg_dump -Fc`) |
| `/status <slug>` | Comprueba conexión a la base y estado vía Management API |
| `/historial <slug>` | Últimos backups del proyecto |

Toda acción queda registrada en `audit_log` y en el historial
(`backup_history`). Un chat no autorizado recibe siempre una respuesta genérica.

## Seguridad

- Credenciales cifradas en reposo con Fernet (clave maestra solo en `.env`).
- Los archivos de backup (`.dump`/`.sql`) se cifran en disco con Fernet
  (`BACKUP_ENCRYPTION_KEY`) y su claro se borra; a Telegram se envían
  descifrados en memoria, sin tocar el disco.
- Contenedores sin privilegios: proceso como usuario no-root (UID 1000),
  capacidades eliminadas (`cap_drop: ALL`), `no-new-privileges` y rootfs de
  solo lectura con `tmpfs` para `/tmp`. El frontend corre nginx sin root
  escuchando en el puerto no privilegiado 8080.
- La API nunca devuelve credenciales completas (solo los últimos 4 caracteres).
- Contraseñas web con PBKDF2-SHA256 (salt por usuario).
- Autenticación API con **tokens JWT** (HS256) enviados como `Authorization: Bearer`.
- Roles web: `admin` (CRUD completo) y `viewer` (solo lectura).
- El slug de cada proyecto se valida contra la whitelist de la base antes de
  usarse en cualquier llamada de sistema.
- La PWA solo guarda el token en `localStorage` del navegador; los datos nunca
  se cachean de forma offline (las llamadas `/api` siempre van a red).
- Cada request revalida el JWT contra la base de datos: si el usuario fue
  desactivado, eliminado o bloqueado, o su rol cambió, la sesión pierde
  acceso al instante (no hace falta esperar a que expire el token).

## Gestión del sistema

```bash
docker compose logs -f backend   # logs de la API + bot
docker compose logs -f frontend  # logs de nginx
docker compose down              # detener (los datos permanecen en ./data)
docker compose up -d             # volver a arrancar
```

## Variables de entorno (`backend/.env`)

| Variable | Descripción |
|---|---|
| `BOT_TOKEN` | Token del bot de Telegram (obligatorio) |
| `ENCRYPTION_KEY` | Clave Fernet para cifrar credenciales (obligatorio) |
| `BACKUP_ENCRYPTION_KEY` | Clave Fernet para cifrar los archivos de backup en disco (obligatorio) |
| `SESSION_SECRET` | Clave HMAC para firmar los JWT (obligatorio) |
| `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` | Solo para crear el primer admin si no hay ninguno |
| `DB_PATH` | Ruta del SQLite (default `/data/backups.db` en Docker) |
| `BACKUP_DIR` | Carpeta de backups (default `/data/backups` en Docker) |
| `BACKUP_KEEP_COUNT` | Rotación: backups a conservar por proyecto (default 10) |
| `BACKUP_TIMEOUT_SECONDS` | Timeout de `pg_dump` en segundos (default 600) |
| `WEB_HOST` / `WEB_PORT` | API interna del backend (default `0.0.0.0:8080`) |
| `CORS_ALLOW_ORIGINS` | Orígenes permitidos al API, separados por coma (default localhost/127.0.0.1:8080) |
| `WEB_DOCS_ENABLED` | Sirve o no Swagger/ReDoc/OpenAPI (default `false`; en producción mantener desactivado) |

## Notas

- Los backups son **solo bajo demanda** (por Telegram). No hay cron/crontab en
  esta versión.
- Las notificaciones son exclusivamente por Telegram: no se ha configurado el
  canal de correo (Resend) a petición del cliente.
- El diseño de `permissions` y `audit_log` deja lista una futura Fase 2 con
  autorregistro de usuarios, límites de uso y filtrado por proyecto.