#!/usr/bin/env bash
# =============================================================================
# Homo Accountant — run the full stack locally.
#
# Two modes:
#   docker (default, recommended)  docker compose dev stack (PG + MinIO + API + web)
#   bare   (--bare)                local PostgreSQL + uvicorn + Next.js dev server
#
# Usage:
#   ./scripts/run-local.sh                 # docker mode (auto-detected)
#   ./scripts/run-local.sh --bare          # bare-metal mode (no docker)
#   ./scripts/run-local.sh --no-build      # skip image/node rebuilds
#   ./scripts/run-local.sh --help
#
# What it does:
#   * creates databases/roles and applies Alembic migrations
#   * seeds demo users (owner@example.com / accountant@example.com / ...)
#   * starts the API on :8000 and the web app on :3000
#   * waits for health endpoints, then prints URLs and demo accounts
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API_PORT="${HOMO_API_PORT:-8000}"
WEB_PORT="${HOMO_WEB_PORT:-3000}"
MODE="docker"
NO_BUILD=0

usage() { sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bare) MODE="bare" ;;
    --no-build) NO_BUILD=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

log()  { printf '\033[1;34m[local]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[local] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"; }

wait_health() { # url name timeout_s
  local url="$1" name="$2" timeout_s="$3"
  for _ in $(seq 1 "$timeout_s"); do
    if curl -fsS "$url" >/dev/null 2>&1; then log "$name is healthy ($url)"; return 0; fi
    sleep 1
  done
  fail "$name did not become healthy within ${timeout_s}s: $url"
}

print_urls() {
  cat <<EOF

────────────────────────────────────────────────────────────────────
  Homo Accountant is running:

    Web:    http://localhost:${WEB_PORT}
    API:    http://localhost:${API_PORT}/api/v1  (docs: http://localhost:${API_PORT}/docs)
    DB:     postgresql://arya:arya_dev_pw@localhost:5432/arya_dev

  Demo users (dev seed):
    owner@example.com      / owner-homo-1405      (مدیر)
    accountant@example.com / acct-homo-1405       (حسابدار)
    staff@example.com      / staff-homo-1405      (کارمند)
    viewer@example.com     / viewer-homo-1405     (بیننده)

  Stop:    docker compose down        (docker mode)
           Ctrl-C / kill the script   (bare mode)
────────────────────────────────────────────────────────────────────
EOF
}

# -----------------------------------------------------------------------------
# Docker mode
# -----------------------------------------------------------------------------
docker_mode() {
  require_cmd docker
  docker compose version >/dev/null 2>&1 || fail "docker compose v2 plugin is required"

  if [[ "$NO_BUILD" -eq 0 ]]; then
    log "building and starting dev stack (PostgreSQL + MinIO + API + web)…"
    docker compose up -d --build db minio api web
  else
    log "starting dev stack without rebuild…"
    docker compose up -d db minio api web
  fi

  # give the API a moment to run migrations at startup, then verify
  for _ in $(seq 1 60); do
    if curl -fsS "http://localhost:${API_PORT}/api/v1/health/ready" >/dev/null 2>&1; then break; fi
    sleep 2
  done
  wait_health "http://localhost:${API_PORT}/api/v1/health/ready" "API" 60
  wait_health "http://localhost:${WEB_PORT}/login" "Web" 90
  print_urls
  log "follow logs with: docker compose logs -f api web"
}

# -----------------------------------------------------------------------------
# Bare-metal mode (local PostgreSQL, no docker)
# -----------------------------------------------------------------------------
bare_mode() {
  require_cmd python3
  require_cmd node
  require_cmd npm
  command -v psql >/dev/null 2>&1 || fail "psql is required in bare mode (install PostgreSQL)"

  local pg_user="${HOMO_PG_USER:-arya}"
  local pg_pw="${HOMO_PG_PASSWORD:-arya_dev_pw}"
  local pg_db="${HOMO_PG_DB:-arya_dev}"
  local pg_test_db="${HOMO_PG_TEST_DB:-arya_test}"

  # --- ensure the role + databases exist (idempotent) ---
  if ! psql -h 127.0.0.1 -U "$pg_user" -d postgres -c "SELECT 1" >/dev/null 2>&1; then
    log "creating role '$pg_user' and databases…"
    sudo -u postgres psql -v ON_ERROR_STOP=1 \
      -c "CREATE ROLE $pg_user WITH LOGIN PASSWORD '$pg_pw' CREATEDB SUPERUSER;" 2>/dev/null || true
    for db in "$pg_db" "$pg_test_db"; do
      sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 ||
        sudo -u postgres createdb -O "$pg_user" "$db"
    done
  fi
  export PGPASSWORD="$pg_pw"

  # --- backend ---
  log "setting up backend venv…"
  cd "$REPO_ROOT/apps/api"
  if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -e ".[dev]" pytest-cov

  log "applying migrations…"
  export HOMO_DATABASE_URL="postgresql+psycopg://$pg_user:$pg_pw@127.0.0.1:5432/$pg_db"
  export HOMO_JWT_SECRET="${HOMO_JWT_SECRET:-dev-only-jwt-secret-change-me-0123456789}"
  export HOMO_CORS_ORIGINS="http://localhost:${WEB_PORT}"
  export HOMO_SEED_DEMO_USERS="true"
  export HOMO_ENVIRONMENT="development"
  alembic upgrade head

  log "starting API on :${API_PORT}…"
  uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" > /tmp/homo-api.log 2>&1 &
  api_pid=$!

  # --- frontend ---
  log "starting web on :${WEB_PORT}…"
  cd "$REPO_ROOT/apps/web"
  if [[ ! -d node_modules ]]; then
    log "installing frontend dependencies (npm ci)…"
    npm ci --no-audit --no-fund
  fi
  NEXT_PUBLIC_API_URL="http://localhost:${API_PORT}/api/v1" npm run dev -- --port "$WEB_PORT" > /tmp/homo-web.log 2>&1 &
  web_pid=$!

  trap 'kill "${api_pid:-}" "${web_pid:-}" 2>/dev/null || true' EXIT INT TERM

  wait_health "http://localhost:${API_PORT}/api/v1/health/ready" "API" 60
  wait_health "http://localhost:${WEB_PORT}/login" "Web" 120
  print_urls
  log "logs: /tmp/homo-api.log  /tmp/homo-web.log"
  log "press Ctrl-C to stop both servers"
  wait
}

# -----------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1 && [[ "$MODE" == "docker" ]]; then
  docker_mode
else
  bare_mode
fi
