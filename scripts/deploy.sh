#!/usr/bin/env bash
# =============================================================================
# Homo Accountant — deploy to a Linux VPS (Ubuntu/Debian) with Docker Compose.
#
# Does, in order:
#   1.  installs Docker Engine + Compose plugin (if missing)
#   2.  clones or updates the repo at APP_DIR (default /opt/homo-accountant)
#   3.  creates .env with generated secrets (never overwrites existing)
#   4.  obtains/refreshes TLS certificates (certbot) unless --no-cert
#   5.  builds and starts the production stack (compose.prod.yaml)
#   6.  waits for health, bootstraps the first admin, prints verification
#
# Usage (run as root or with sudo):
#   sudo ./scripts/deploy.sh --domain your.domain --email you@example.com
#   sudo ./scripts/deploy.sh --domain your.domain --email you@example.com \
#        --repo git@github.com:faraz-fatahnaie/homo-accountant.git
#   sudo ./scripts/deploy.sh --update            # pull + rebuild + restart
#   sudo ./scripts/deploy.sh --domain your.domain --no-cert --skip-build
# =============================================================================
set -euo pipefail

APP_DIR="/opt/homo-accountant"
REPO_URL="https://github.com/faraz-fatahnaie/homo-accountant.git"
DOMAIN=""
CERT_EMAIL=""
DO_CERT=1
SKIP_BUILD=0
UPDATE_ONLY=0

usage() { sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="${2:?--domain requires a value}"; shift 2 ;;
    --email) CERT_EMAIL="${2:?--email requires a value}"; shift 2 ;;
    --repo) REPO_URL="${2:?--repo requires a value}"; shift 2 ;;
    --app-dir) APP_DIR="${2:?--app-dir requires a value}"; shift 2 ;;
    --no-cert) DO_CERT=0; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --update) UPDATE_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$(id -u)" -eq 0 ]] || { echo "run as root (or with sudo)" >&2; exit 1; }

log()  { printf '\033[1;32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy] WARN:\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[deploy] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"; }

# ---------------------------------------------------------------------------
# 1. Docker
# ---------------------------------------------------------------------------
ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "docker + compose plugin already installed"
    return
  fi
  log "installing Docker Engine + compose plugin…"
  apt-get update -qq
  apt-get install -y -qq docker.io docker-compose-v2
  systemctl enable --now docker
  require_cmd docker
  docker compose version >/dev/null 2>&1 || fail "docker compose plugin not available"
}

# ---------------------------------------------------------------------------
# 2. Repo
# ---------------------------------------------------------------------------
ensure_repo() {
  if [[ -d "$APP_DIR/.git" ]]; then
    log "updating repo at $APP_DIR (git pull)…"
    git -C "$APP_DIR" pull --ff-only
  else
    log "cloning $REPO_URL -> $APP_DIR …"
    git clone "$REPO_URL" "$APP_DIR"
  fi
  cd "$APP_DIR"
}

# ---------------------------------------------------------------------------
# 3. .env
# ---------------------------------------------------------------------------
random_hex() { openssl rand -hex 32; }

ensure_env() {
  [[ -f "$APP_DIR/.env" ]] && { log ".env already exists — leaving it untouched"; return; }
  log "creating .env from template with generated secrets…"
  cp .env.example .env

  local secret
  secret="$(random_hex)"; sed -i "s|^HOMO_JWT_SECRET=.*|HOMO_JWT_SECRET=$secret|" .env
  secret="$(random_hex)"; sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$secret|" .env
  secret="$(random_hex)"; sed -i "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$secret|" .env

  if [[ -n "$DOMAIN" ]]; then
    sed -i "s|^HOMO_CORS_ORIGINS=.*|HOMO_CORS_ORIGINS=https://$DOMAIN|" .env
  fi
  chmod 600 .env
  warn "edit $APP_DIR/.env and set:"
  warn "  HOMO_ADMIN_BOOTSTRAP_EMAIL / HOMO_ADMIN_BOOTSTRAP_PASSWORD (first admin)"
  warn "  HOMO_CORS_ORIGINS (current: $(grep '^HOMO_CORS_ORIGINS=' .env | cut -d= -f2))"
}

# ---------------------------------------------------------------------------
# 4. TLS certificates
# ---------------------------------------------------------------------------
ensure_certs() {
  if [[ "$DO_CERT" -eq 0 ]]; then
    warn "--no-cert: skipping certbot; provide certs at $APP_DIR/infra/nginx/ssl/"
    return
  fi
  [[ -n "$DOMAIN" ]] || { warn "no --domain given; skipping TLS setup (provide certs manually)"; return; }
  if ! command -v certbot >/dev/null 2>&1; then
    log "installing certbot…"
    apt-get update -qq
    apt-get install -y -qq certbot
  fi
  log "obtaining/refreshing Let's Encrypt certificate for $DOMAIN …"
  mkdir -p "$APP_DIR/infra/nginx/ssl"
  local cert_args=()
  [[ -n "$CERT_EMAIL" ]] && cert_args+=(--email "$CERT_EMAIL")
  certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos \
    --keep-until-expiring "${cert_args[@]}"
  cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$APP_DIR/infra/nginx/ssl/fullchain.pem"
  cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem"   "$APP_DIR/infra/nginx/ssl/privkey.pem"
  chmod 600 "$APP_DIR/infra/nginx/ssl/privkey.pem"
  install -d /etc/letsencrypt/renewal-hooks/pre /etc/letsencrypt/renewal-hooks/post
  cat > /etc/letsencrypt/renewal-hooks/pre/homo-accountant-nginx <<EOF
#!/usr/bin/env bash
docker compose -f "$APP_DIR/compose.prod.yaml" stop nginx >/dev/null 2>&1 || true
EOF
  cat > /etc/letsencrypt/renewal-hooks/post/homo-accountant-nginx <<EOF
#!/usr/bin/env bash
set -e
cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$APP_DIR/infra/nginx/ssl/fullchain.pem"
cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$APP_DIR/infra/nginx/ssl/privkey.pem"
chmod 600 "$APP_DIR/infra/nginx/ssl/privkey.pem"
docker compose -f "$APP_DIR/compose.prod.yaml" up -d nginx
EOF
  chmod 700 /etc/letsencrypt/renewal-hooks/{pre,post}/homo-accountant-nginx
  log "certificates copied to infra/nginx/ssl/"
}

# ---------------------------------------------------------------------------
# 5. Build + start
# ---------------------------------------------------------------------------
start_stack() {
  if [[ "$SKIP_BUILD" -eq 0 ]]; then
    log "building images and starting stack…"
    docker compose -f compose.prod.yaml up -d --build
  else
    log "starting stack without rebuild…"
    docker compose -f compose.prod.yaml up -d
  fi

  log "waiting for API health…"
  for _ in $(seq 1 90); do
    if docker compose -f compose.prod.yaml exec -T api \
       python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready')" \
       >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  docker compose -f compose.prod.yaml exec -T api \
    python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready')" \
    >/dev/null || {
    docker compose -f compose.prod.yaml logs api | tail -40 >&2
    fail "API did not become healthy"
  }
  if [[ -n "$DOMAIN" && "$DO_CERT" -eq 1 ]]; then
    curl -kfsS --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/healthz" >/dev/null || {
      docker compose -f compose.prod.yaml logs nginx | tail -40 >&2
      fail "nginx HTTPS health check failed"
    }
    curl -kfsS --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/login" >/dev/null \
      || fail "web login page health check failed"
  fi
  log "API healthy"
}

# ---------------------------------------------------------------------------
# 6. Bootstrap + verify
# ---------------------------------------------------------------------------
bootstrap_and_verify() {
  local admin_email admin_pw
  admin_email="$(grep '^HOMO_ADMIN_BOOTSTRAP_EMAIL=' .env | cut -d= -f2)"
  admin_pw="$(grep '^HOMO_ADMIN_BOOTSTRAP_PASSWORD=' .env | cut -d= -f2)"
  if [[ -n "$admin_email" && -n "$admin_pw" ]]; then
    log "bootstrapping first admin ($admin_email)…"
    docker compose -f compose.prod.yaml exec -T api python -m app.scripts.bootstrap_admin \
      || warn "bootstrap_admin failed (already bootstrapped?) — verify the owner account"
    sed -i 's|^HOMO_ADMIN_BOOTSTRAP_EMAIL=.*|HOMO_ADMIN_BOOTSTRAP_EMAIL=|' .env
    sed -i 's|^HOMO_ADMIN_BOOTSTRAP_PASSWORD=.*|HOMO_ADMIN_BOOTSTRAP_PASSWORD=|' .env
    docker compose -f compose.prod.yaml up -d --no-deps api
    log "bootstrap credentials removed from .env and API environment"
  else
    warn "HOMO_ADMIN_BOOTSTRAP_* not set — create the first admin manually:"
    warn "  docker compose -f compose.prod.yaml exec api python -m app.scripts.bootstrap_admin"
  fi

  cat <<EOF

────────────────────────────────────────────────────────────────────
  Deploy complete.

    https://$DOMAIN/            web app (nginx, TLS)
    https://$DOMAIN/api/v1/health/ready   API health
    https://$DOMAIN/api/        API (proxied by nginx)

  Operations:
    logs:   docker compose -f compose.prod.yaml logs -f api web
    backup: 0 2 * * * $APP_DIR/infra/backup/backup.sh /mnt/backups
    update: $APP_DIR/scripts/deploy.sh --update
    status: docker compose -f compose.prod.yaml ps
────────────────────────────────────────────────────────────────────
EOF
}

# ---------------------------------------------------------------------------
log "== Homo Accountant deploy =="
ensure_docker
if [[ "$UPDATE_ONLY" -eq 1 ]]; then
  ensure_repo
  ensure_env
  start_stack
  log "update finished"
else
  ensure_repo
  ensure_env
  ensure_certs
  start_stack
  bootstrap_and_verify
fi
