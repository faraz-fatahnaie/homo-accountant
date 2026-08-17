#!/usr/bin/env bash
# ============================================================
# Restore PostgreSQL dump produced by backup.sh.
# Usage: ./infra/backup/restore.sh /path/to/homo-accountant-<ts>
#        ./infra/backup/restore.sh /path/to/homo-accountant-<ts>/db.dump.gz
# DANGER: overwrites the current database. Test on a scratch DB first.
# ============================================================
set -euo pipefail

INPUT="${1:?usage: restore.sh <backup-directory|db.dump.gz>}"
if [ -d "$INPUT" ]; then
  BACKUP_ROOT="$INPUT"
  DUMP="$BACKUP_ROOT/db.dump.gz"
else
  DUMP="$INPUT"
  BACKUP_ROOT="$(dirname "$DUMP")"
fi
[ -f "$DUMP" ] || { echo "dump not found: $DUMP" >&2; exit 1; }
COMPOSE="docker compose -f compose.prod.yaml"
DB_CONTAINER=$($COMPOSE ps -q db)
[ -n "$DB_CONTAINER" ] || { echo "db container not running" >&2; exit 1; }
API_CONTAINER=$($COMPOSE ps -aq api | head -1)

POSTGRES_USER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)
POSTGRES_DB=$(grep '^POSTGRES_DB=' .env | cut -d= -f2)

echo "[restore] target db: $POSTGRES_DB (container $DB_CONTAINER)"
read -r -p "This overwrites the database. Type 'restore' to continue: " CONFIRM
[ "$CONFIRM" = "restore" ] || { echo "aborted"; exit 1; }

$COMPOSE stop api

gunzip -c "$DUMP" | docker exec -i "$DB_CONTAINER" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner --no-privileges

if [ -d "$BACKUP_ROOT/media" ] && [ -n "$API_CONTAINER" ]; then
  $COMPOSE run --rm --no-deps api sh -c 'find /srv/api/media -mindepth 1 -delete'
  docker cp "$BACKUP_ROOT/media/." "$API_CONTAINER:/srv/api/media/"
  echo "[restore] attachments restored"
fi

$COMPOSE start api
echo "[restore] done; verify health/ready and sample financial records."
