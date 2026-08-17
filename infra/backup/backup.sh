#!/usr/bin/env bash
# ============================================================
# PostgreSQL + attachment backup for the Homo Accountant stack.
# Usage: ./infra/backup/backup.sh [backup-dir]
# Retention: keep KEEP_DAILY daily backups + KEEP_WEEKLY weekly (defaults below).
# Cron example (VPS): 0 2 * * * /opt/homo-accountant/infra/backup/backup.sh /mnt/backups >> /var/log/homo-accountant-backup.log 2>&1
# ============================================================
set -euo pipefail

BACKUP_DIR="${1:-$(dirname "$0")/../../backups}"
KEEP_DAILY="${KEEP_DAILY:-14}"
KEEP_WEEKLY="${KEEP_WEEKLY:-8}"
COMPOSE="docker compose -f compose.prod.yaml"
TS="$(date +%Y%m%d-%H%M%S)"
STAMP="$BACKUP_DIR/homo-accountant-$TS"

mkdir -p "$STAMP"

echo "[backup] $(date -Is) starting"

# --- PostgreSQL ---
DB_CONTAINER=$($COMPOSE ps -q db)
if [ -z "$DB_CONTAINER" ]; then
  echo "[backup] ERROR: db container not running" >&2
  exit 1
fi
POSTGRES_USER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)
POSTGRES_DB=$(grep '^POSTGRES_DB=' .env | cut -d= -f2)
docker exec "$DB_CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner \
  > "$STAMP/db.dump"
gzip -f "$STAMP/db.dump"
echo "[backup] db.dump.gz: $(du -h "$STAMP/db.dump.gz" | cut -f1)"

# --- Uploaded attachments (persistent API media volume) ---
API_CONTAINER=$($COMPOSE ps -q api)
if [ -n "$API_CONTAINER" ]; then
  mkdir -p "$STAMP/media"
  docker cp "$API_CONTAINER:/srv/api/media/." "$STAMP/media/"
  echo "[backup] media: $(du -sh "$STAMP/media" | cut -f1)"
else
  echo "[backup] ERROR: api container not running; attachments were not backed up" >&2
  exit 1
fi

# --- Compose file snapshot (config reproducibility) ---
cp compose.prod.yaml .env.example "$STAMP/" 2>/dev/null || true

# --- Retention: daily ---
find "$BACKUP_DIR" -maxdepth 1 -type d -name 'homo-accountant-*' -mtime "+$KEEP_DAILY" -exec rm -rf {} +

# --- Weekly archive (monday) ---
if [ "$(date +%u)" = "1" ]; then
  find "$BACKUP_DIR" -maxdepth 1 -type d -name 'homo-accountant-*' -mtime "+$((KEEP_WEEKLY*7))" -exec rm -rf {} +
fi

echo "[backup] done -> $STAMP"
echo "[backup] remember: copy this directory off-server (scp/rclone) for offsite retention."
