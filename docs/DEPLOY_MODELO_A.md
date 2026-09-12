# Despliegue "Modelo A" + Runbook

Objetivo: una copia privada del panel en una **VM Oracle Cloud (Always Free, Ubuntu
22.04/24.04)** accesible **solo por Tailscale** (sin exponer puertos a Internet), con
backups locales cifrados y, si se configura, copia fuera del sitio (R2/S3/B2). Este
mismo compose funciona en un VPS cualquiera; la diferencia es que aquí **nada escucha
en `0.0.0.0:8080` público** (el bind ya es `127.0.0.1:8080`).

---

## 1. Secretos: vault antes que nada

Antes de desplegar, guarda las claves en un vault (`pass` con una GPG key privada, o
`sops` + KMS/age). **Sin las claves de abajo no se puede recuperar nada**:

| Clave | De dónde sale | Si la pierdes |
|---|---|---|
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | No descifras credenciales de la BD del panel |
| `BACKUP_ENCRYPTION_KEY` | igual que arriba | No descifras NI UN solo backup `.dump.enc`/`.sql.enc` |
| `SESSION_SECRET` | `openssl rand -hex 32` | Todos los JWT quedan inválidos (sesiones caídas) — no pierdes datos |
| `BOT_TOKEN` | BotFather | El bot deja de funcionar |
| `WEB_ADMIN_USERNAME/PASSWORD` | tú | Adjunta login inicial |

Recomendado: `pass`.

```bash
sudo apt install -y pass gnupg
gpg --full-generate-key        # clave "master" de respaldo (haz un export offline)
pass init <tu-gpg-key-id>
pass insert backups-supabase/ENCRYPTION_KEY
# ... una entrada por variable ...
```

El `.env` del servidor se genera una sola vez y se **cifra** en reposo en el propio
servidor; recuerda que también lo tienes en el vault. No commitees `.env` (ya está en
`.gitignore`).

---

## 2. Create la VM Oracle Free

- Compute → Instances → Create: Ubuntu 24.04 (Always Free, ARM Ampere A1 o VM.Standard.E2.1.Micro x86).
- Sube tu **clave SSH pública** (o usa las claves de Oracle).
- VCN/Subnet pública: no hace falta abrir puertos de entrada al panel.

## 3. Instala Docker y Tailscale en la VM

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh            # inicia sesión con la cuenta de Tailnet
sudo tailscale serve --bg 8080     # ¡esto expone http://<tailnet-ip>/ -> localhost:8080
```

`tailscale serve` entrega **HTTPS automático** (`https://<maquina>.<tailnet>.ts.net`)
sin configurar certificados. El panel queda SOLO accesible para nodos de tu tailnet.

## 4. Despliega la aplicación

```bash
git clone <tu-repo> backups-supabase && cd backups-supabase
cp backend/.env.example backend/.env
# Edita backend/.env: completa las claves del vault, WEB_ADMIN_*, BOT_TOKEN, etc.
docker compose up -d --build
docker compose ps            # ambos "healthy"
```

Opcional (recomendado si hay disk fuera): activa la copia off-site en `.env`:

```txt
OFFSITE_ENABLED=on
OFFSITE_ENDPOINT=https://ACCOUNT.r2.cloudflarestorage.com
OFFSITE_REGION=auto
OFFSITE_ACCESS_KEY=...
OFFSITE_SECRET_KEY=...
OFFSITE_BUCKET=panel-backups
OFFSITE_PREFIX=vm1
OFFSITE_KEEP_COUNT=30
docker compose restart backend    # la subida inicial corre al arrancar
```

## 5. Verifica

```bash
curl -s https://NORMA.<tailnet>.ts.net/api/health   # {"status":"ok"}
sudo tailscale status
docker logs supabase-backups-api --tail 30
```

---

## Operaciones de rutina

| Tarea | Comando |
|---|---|
| Backup manual de un proyecto | En el chat del bot: `/backup <slug>` |
| Health | `curl -s localhost:8080/api/health` |
| Logs | `docker logs -f supabase-backups-api` |
| Self-backup de la BD del panel | Se hace solo: `data/backups/self/panel_*.sqlite.enc` cada día a las 03:00 UTC |
| Resumen diario | Llega por Telegram a las 08:00 UTC (estado por proyecto + alertas) |
| Off-site | Tras cada backup con éxito se suben los `.enc` nuevos a R2/S3/B2 |
| Actualizar | `git pull && docker compose up -d --build` |

## Restaurar un backup `.enc`

```bash
# En un contenedor (u host) con la misma BACKUP_ENCRYPTION_KEY:
docker cp data/backups/<slug>/<archivo>.dump.enc supabase-backups-api:/tmp/x.enc
docker exec supabase-backups-api python - <<'PY'
from pathlib import Path
from core import crypto
p = Path("/tmp/x.enc")
Path("/tmp/restaurado.dump").write_bytes(crypto.decrypt_file_bytes(p))
print("escrito", Path("/tmp/restaurado.dump").stat().st_size, "bytes")
PY
# pg_restore restaurado.dump ...
```

Los `.dump` son `pg_dump -Fc` (custom, comprimidos); los `.sql` son formato plano.

---

## Runbook de incidentes

### 1. El bot deja de responder
1. `docker compose ps` → si no `healthy`, `docker compose logs backend`.
2. Comprueba `BOT_TOKEN` en `.env` (¿lo regeneraste en BotFather por error?).
3. `docker compose restart backend` no es la causa raíz: mira el log de `telegram.ext.Application`.

### 2. "Espacio en disco insuficiente" / disco lleno
1. `df -h` y `du -sh data/backups/* | sort -h`.
2. Baja `BACKUP_KEEP_COUNT` / la frecuencia de crons. Libera `data/backups/self` (rotación ya aplica).
3. La guarda `BACKUP_MIN_FREE_MB` aborta backups ANTES de llenar el disco: no la desactives.

### 3. "No se pudo descifrar el backup"
- La `BACKUP_ENCRYPTION_KEY` cambió o el archivo está corrupto. **No** reintentes borrando:
  los `.enc` sin descifrar se conservan. Recupera la clave del vault y restáuralos.

### 4. Barrido de claros a la arrancada
- El log `Se encontraron backups SIN CIFRAR ... eliminados` indica un proceso muerto a
  mitad de un backup. Normal: el proceso siguiente se limpia solo. Si se repite mucho,
  revisa timeouts (`BACKUP_TIMEOUT_SECONDS`) y que no se reinicie el contenedor a la vez.

### 5. Sospecha de fuerza bruta al panel
- Si el backend alerta `Posible ataque de fuerza bruta`/`Tráfico sospechoso`, revisa los
  logs por la IP reportada. El acceso real va por `tailscale serve`, con nginx
  confiando solo en `set_real_ip_from` del loopback: IPs spoofeadas no engañan al rate-limit.

---