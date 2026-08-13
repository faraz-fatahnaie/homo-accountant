# استقرار — Deployment runbook (Linux VPS, Docker Compose)

## 1. Prerequisites

- Ubuntu 22.04/24.04 (or Debian 12) VPS, ≥ 2 vCPU / 4 GB RAM, 30 GB disk.
- Domain name pointing to the VPS IP (A record).
- Docker Engine + Compose plugin installed.

## 2. First deploy

```bash
# as root or a sudo user
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker

# checkout the release
git clone <your-repo-url> /opt/homo-accountant && cd /opt/homo-accountant
git checkout <release-tag-or-sha>

cp .env.example .env
# EDIT .env: strong HOMO_JWT_SECRET (openssl rand -hex 32),
#           POSTGRES_PASSWORD, MINIO_* secrets,
#           HOMO_ADMIN_BOOTSTRAP_EMAIL / HOMO_ADMIN_BOOTSTRAP_PASSWORD,
#           HOMO_CORS_ORIGINS=https://your.domain

# TLS certificates (choose one):
#  a) certbot:   sudo apt install -y certbot && sudo certbot certonly --nginx -d your.domain
#     then: mkdir -p infra/nginx/ssl && cp /etc/letsencrypt/live/your.domain/{fullchain.pem,privkey.pem} infra/nginx/ssl/
#  b) DNS-01 challenge for wildcards (documented separately).
# NOTE: nginx requires certs to start. For first bring-up without certs,
# comment the 443 server block or provide self-signed certs temporarily.

docker compose -f compose.prod.yaml up -d --build

# verify
curl -sf https://your.domain/api/v1/health/ready && echo OK
curl -sf https://your.domain/login && echo OK
```

## 3. Bootstrap the first admin

```bash
docker compose -f compose.prod.yaml exec api python -m app.scripts.bootstrap_admin
# -> creates the OWNER from HOMO_ADMIN_BOOTSTRAP_EMAIL/PASSWORD
# then immediately rotate the password via the UI/user management.
```

## 4. Upgrades

```bash
git pull && git checkout <new-sha>
docker compose -f compose.prod.yaml build api web
docker compose -f compose.prod.yaml up -d
# migrations run automatically at API start (alembic upgrade head)
# rollback: checkout previous sha, rebuild, up -d (migrations are forward-only:
# a schema downgrade needs a documented manual step — never force it)
```

## 5. Backups & restore

See `infra/backup/backup.sh` + `restore.sh`, and `docs/operations.md` (schedule via cron,
offsite copy mandatory).

## 6. Common failures

| Symptom | Cause / fix |
|---|---|
| nginx won't start | missing TLS certs → provide certs or disable 443 block |
| API unhealthy | DB not ready / migrations failed → `docker compose -f compose.prod.yaml logs api` |
| 502 on /api/ | api container restarting → check `health/ready` + logs |
| Uploads fail | MinIO bucket not created → create `homo-accountant-attachments` bucket once |
| 429 on login | rate limit — expected; check for brute-force attempts in logs |

## 7. Publishing images / CI deployment

The `docker.yml` `publish` job is **disabled by default** (`if: ${{ false }}`). To enable:
configure a registry (GHCR/Docker Hub) token as a secret, review the job, and explicitly
authorize — per project policy, nothing is published or deployed without owner credentials
and approval.
