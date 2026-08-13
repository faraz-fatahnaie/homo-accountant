#!/usr/bin/env bash
# ============================================================
# Restore PostgreSQL dump produced by backup.sh.
# Usage: ./infra/backup/restore.sh /path/to/homo-accountant-<ts>/db.dump.gz
# DANGER: overwrites the current database. Test on a scratch DB first.
# ============================================================
set -euo pipefail

DUMP="${1:?usage: restore.sh <db.dump.gz>}"
COMPOSE="docker compose -f compose.prod.yaml"
DB_CONTAINER=$($COMPOSE ps -q db)
[ -n "$DB_CONTAINER" ] || { echo "db container not running" >&2; exit 1; }

POSTGRES_USER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)
POSTGRES_DB=$(grep '^POSTGRES_DB=' .env | cut -d= -f2)

echo "[restore] target db: $POSTGRES_DB (container $DB_CONTAINER)"
read -r -p "This overwrites the database. Type 'restore' to continue: " CONFIRM
[ "$CONFIRM" = "restore" ] || { echo "aborted"; exit 1; }

gunzip -c "$DUMP" | docker exec -i "$DB_CONTAINER" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner --no-privileges

echo "[restore] done. Restart api so it reconnects cleanly:"
echo "  docker compose -f compose.prod.yaml restart api"
