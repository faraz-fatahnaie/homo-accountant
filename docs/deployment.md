# استقرار — Deployment runbook (Linux VPS, Docker Compose)

> **Quick start (recommended):** use the packaged scripts instead of the manual steps below.
> - Local development: `./scripts/run-local.sh` (docker mode) or `--bare` (local PostgreSQL)
> - First deploy: `sudo ./scripts/deploy.sh --domain your.domain --email you@example.com`
> - Upgrade: `sudo ./scripts/deploy.sh --update`
>
> The manual steps below document exactly what the scripts do.

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

## 7b. CI/CD workflows (verified in slice 9 packaging)

- `ci.yml` — backend (ruff/mypy/pytest+coverage on PG16), frontend (eslint/tsc/vitest
  --coverage/build), and `contract-drift` (regenerates the OpenAPI client and fails on drift).
  Requires `@vitest/coverage-v8` (present) and the api-client `generate` script (simplified).
- `security.yml` — pip-audit on the lockfile (verified 0 findings), strict `npm audit`
  (0 vulnerabilities), trufflehog secret scan, CodeQL.
- `docker.yml` — builds api+web, boots the prod stack via `.github/compose.smoke.yaml`
  (publishes :8000/:3000 for smoke tests; prod compose keeps ports nginx-only), scans both
  images with trivy (fails only on FIXABLE HIGH/CRITICAL via `ignore-unfixed`; documented
  accepts go in `.trivyignore`). Publish/deploy stays disabled until the owner adds registry
  credentials.
- **Base images are pinned to digests** (python:3.12-slim, node:20-alpine in the Dockerfiles;
  postgres:16-alpine, minio, nginx in compose.prod.yaml) for reproducible, supply-chain-safe
  builds. To update, bump the digest after `docker pull <image>` and re-run the Docker
  workflow (the Dockerfile `# bump:` comments mark every pin). The weekly schedule re-runs
  scans; it does NOT silently change images.
- `e2e.yml` — full Playwright suite (78 tests, desktop+mobile) against the dev compose stack.
- **Lockfile is Python-3.12-safe**: `requirements.txt` pins resolve on 3.12 (greenlet 3.2.5),
  matching CI and the `python:3.12-slim` Docker image. If regenerating the lockfile, verify
  with: `pip download -r requirements.txt --only-binary=:all: --python-version 3.12
  --implementation cp --platform manylinux_2_17_x86_64`.

## 8. Security updates (slice 9)

- **Keep Next.js patched:** the app pins `next@15.5.23` (CVE-2025-66478 React2Shell and the
  July 2026 advisories are only fixed in 15.5.21+ / 16.2.11+ — 15.3.x is NOT patched). Before
  each release run `npm audit` in `apps/web` (0 vulnerabilities expected) and
  `pip-audit`/`pip install --upgrade` in `apps/api`.
- **CSP** is delivered by `apps/web/src/middleware.ts` (per-request). Do NOT move it into
  `next.config.ts` headers — a static CSP breaks Next.js RSC inline scripts (verified).
- **Uploads** are magic-byte validated server-side; the declared content-type is never trusted.
- **Certs** live in `infra/nginx/ssl/` (gitignored) — never commit them.
- OpenAPI contract snapshot: `packages/api-client/src/schema.d.ts` is committed and checked for
  drift in CI (`ci.yml` → contract-drift); regenerate with `npm run generate` when routes change.
