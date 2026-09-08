# Prompt para agente de IA: Bot de Backups y Monitoreo de Supabase (Multiplataforma)

Copia y pega este prompt completo en Claude Code (o el agente que estés usando) para arrancar el proyecto.

---

## Prompt

Quiero que me ayudes a construir un sistema multiplataforma (debe poder correr igual en Linux, macOS y Windows) con dos partes que trabajan juntas:

1. **Un bot de Telegram en Python** para disparar backups bajo demanda, listar proyectos conectados, consultar el estado de un proyecto, y recibir notificaciones.
2. **Una interfaz web de administración** para agregar, editar y eliminar conexiones a proyectos de Supabase, sin tocar código ni archivos de configuración manualmente.

Los proyectos que voy a respaldar van a cambiar con el tiempo, así que la gestión de conexiones tiene que ser dinámica desde la interfaz, no fija en un `.env`.

### Contexto técnico y requisito de multiplataforma

- El sistema debe funcionar igual en Linux, macOS y Windows. Para lograrlo:
  - **Nada de scripts bash ni PowerShell.** Toda la lógica de sistema (backup con `pg_dump`, compresión, rotación de archivos) se implementa en Python puro, usando `subprocess.run(["pg_dump", ...], shell=False)` para invocar el binario directamente, sin pasar por una shell.
  - **Rutas de archivos con `pathlib.Path`**, nunca rutas escritas a mano con `/` o `\`, para que la generación de carpetas y nombres de backup funcione igual en cualquier sistema operativo.
  - **Docker como método de despliegue principal.** Un `Dockerfile` basado en una imagen de Python que incluya `postgresql-client` (para tener `pg_dump` disponible), más un `docker-compose.yml` que levante el bot y la interfaz web juntos, con `restart: unless-stopped` para que se mantengan activos sin depender de systemd, launchd, o el Programador de tareas de Windows.
  - Documentar también, como alternativa opcional (no como método principal), cómo correr el proyecto sin Docker directamente en cada sistema operativo: systemd en Linux, launchd en macOS, Programador de tareas en Windows.
- Backend y bot: Python (`python-telegram-bot` para el bot).
- Interfaz web de administración: FastAPI con un frontend simple (HTML/Tailwind sin frameworks pesados), servido por el mismo backend.
- Base de datos: SQLite para empezar (proyectos, cuentas, permisos, logs), con la capa de acceso a datos desacoplada por si en el futuro se migra a Postgres.
- **Los backups son solo bajo demanda**, disparados exclusivamente por comando del bot de Telegram. No hay backups automáticos por cron en esta primera versión.

### Arquitectura general

**1. Interfaz web de administración (`admin_web/`)**

- Panel protegido con login simple (usuario y contraseña).
- Funciones:
  - Listar proyectos conectados (nombre, cuenta asociada, fecha de creación, último backup realizado).
  - Agregar proyecto nuevo: nombre/slug, cuenta de Supabase asociada (o crear una cuenta nueva), cadena de conexión a PostgreSQL (pooler), referencia del proyecto (`project_ref`) para la Management API.
  - Editar proyecto existente.
  - Eliminar proyecto (con confirmación, dejando rastro en el log de auditoría, sin borrar el historial de backups asociados).
  - Gestionar cuentas de Supabase (agregar/editar/eliminar Personal Access Tokens).
- Las credenciales sensibles se encriptan en reposo con `cryptography` (Fernet) antes de guardarse en SQLite. La clave maestra vive solo en el `.env` del contenedor, nunca en la base de datos ni en la interfaz.
- La interfaz nunca muestra credenciales completas una vez guardadas (solo los últimos caracteres, con opción de reemplazo completo).

**2. Base de datos (`db/`)**

- Tabla `accounts`: cuentas de Supabase, con PAT encriptado.
- Tabla `projects`: proyectos individuales (`id`/slug, `account_id`, cadena de conexión encriptada, `project_ref`, `activo`).
- Tabla `users` (para el bot de Telegram): `telegram_chat_id`, `nombre`, `rol`, `activo`.
- Tabla `permissions`: `user_id`, `project_id`, `can_backup`, `can_monitor`. Diseñada desde el inicio aunque hoy solo la uses tú con permisos totales, para poder sumar más usuarios en el futuro sin rediseñar nada.
- Tabla `backup_history`: `project_id`, `fecha`, `tamaño_archivo`, `resultado`, `ruta_archivo`.
- Tabla `audit_log`: `user_id`, `project_id`, `accion`, `resultado`, `timestamp`.

**3. Bot de Telegram (`bot/`)**

Comandos principales:

- `/proyectos`: lista todos los proyectos activos conectados, con su slug y la fecha del último backup.
- `/backup <slug>`: dispara el backup del proyecto indicado, validando que el `chat_id` esté autorizado y que el proyecto exista y esté activo. El slug se valida contra la whitelist de la base de datos antes de usarse en cualquier llamada a `subprocess`.
- `/status <slug>`: consulta el estado actual del proyecto (conexión a la base de datos y, si aplica, estado vía Management API con el PAT de la cuenta correspondiente).
- `/historial <slug>`: muestra los últimos backups realizados sobre ese proyecto.

Flujo de validación en cada comando:

1. Extraer `chat_id` del mensaje.
2. Si no está en `users` o está inactivo, responder un mensaje genérico de "no autorizado", sin revelar si el proyecto existe.
3. Si el usuario es válido, verificar el permiso específico (`can_backup` o `can_monitor`) sobre el proyecto solicitado.
4. Ejecutar la acción solo si pasa la validación, y registrar el resultado en `audit_log`.

**4. Módulo de backups (`backup/`)**

- Escrito en Python puro (sin scripts externos de shell). Al recibir `/backup <slug>` autorizado, resuelve internamente la cadena de conexión real desde la base de datos y ejecuta `pg_dump` vía `subprocess.run` con los argumentos como lista (nunca como string concatenado), en formato comprimido (`-Fc`).
- Nombra el archivo con fecha y hora usando `pathlib`, y aplica rotación (mantener los últimos N backups por proyecto, configurable).
- Verifica que el archivo generado no esté vacío y que el proceso haya terminado con código de salida 0 antes de reportar éxito.
- Notifica en el mismo chat que originó el comando: éxito con detalles (tamaño, ubicación, duración) o error con el detalle del fallo.
- Registra el resultado en `backup_history` y en `audit_log`.

**5. Notificaciones (`notify/`)**

- Canal principal: respuesta directa en el chat de Telegram que originó la acción.
- Opcional: correo vía Resend como respaldo para fallos.

### Requisitos no funcionales

- Manejo de errores explícito en cada paso, sin fallos silenciosos.
- Logs claros con timestamp, en consola y archivo.
- Credenciales sensibles (clave maestra de encriptación, token del bot, credenciales del login web, credenciales de Resend) solo en `.env`, nunca hardcodeadas.
- Código organizado en módulos separados según lo descrito, con `main.py` para el bot y la app de FastAPI para la interfaz web (pueden compartir proceso o correr como servicios separados dentro del mismo `docker-compose.yml`, tú decides y justificas cuál conviene).
- Incluir `README.md` con instalación vía Docker (método principal), cómo registrar el bot de Telegram, y una sección aparte con instrucciones nativas por sistema operativo como alternativa opcional.

### Entregables esperados

1. Estructura de carpetas del proyecto (bot, interfaz web, lógica de backup, base de datos).
2. Esquema de la base de datos SQLite (script de creación de tablas).
3. Interfaz web funcional para gestionar cuentas y proyectos (CRUD completo).
4. Bot de Telegram funcional con los comandos descritos.
5. Módulo de backup en Python puro con rotación.
6. `Dockerfile` y `docker-compose.yml` listos para levantar todo con un solo comando.
7. Archivo `.env.example` documentado.
8. README con instalación vía Docker y alternativas nativas por sistema operativo.

### Preguntas antes de empezar

Antes de escribir código, pregúntame:
- Si prefiero login simple por contraseña o algo más robusto para la interfaz web.
- Cuántos backups quiero conservar por proyecto (rotación).
- Si quiero que las notificaciones de backup fallido también lleguen por correo además de Telegram.
- Puerto en el que debe exponerse la interfaz web dentro de Docker.

---

## Notas para ti (Walther)

- Con Docker como método principal, no importa si terminas corriendo esto en tu Ultramarine Linux, en un VPS, o si algún compañero del Club de IA lo quiere levantar en Windows con Docker Desktop: el comportamiento va a ser el mismo en todos lados.
- El diseño con tabla de permisos y `audit_log` desde el inicio deja el camino libre para una futura Fase 2 donde el bot se abra a más usuarios (con alta de usuarios, filtrado de proyectos por usuario y límites de uso), sin rehacer la base del proyecto.
- Si quieres, puedo ayudarte a definir las respuestas de la última sección ahora mismo y armar el proyecto aquí directamente en lugar de solo entregarte el prompt.
