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
sudo apt update && sudo apt install -y docker.io docker-compose-v2
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
#  a) certbot:   sudo apt install -y certbot && sudo certbot certonly --standalone -d your.domain
#     then: mkdir -p infra/nginx/ssl && cp /etc/letsencrypt/live/your.domain/{fullchain.pem,privkey.pem} infra/nginx/ssl/
#  b) DNS-01 challenge for wildcards (documented separately).
# NOTE: nginx requires certs to start. For first bring-up without certs,
# comment the 443 server block or provide self-signed certs temporarily.

docker compose -f compose.prod.yaml up -d --build

# verify
curl -sf https://your.domain/api/v1/health/ready && echo OK
curl -sf https://your.domain/login && echo OK
```

### Temporary HTTP-only deployment

When only port 80 is available, use the explicit override below. This does not publish ports
3000, 8000, or 5432 and does not require certificate files:

```bash
docker compose -f compose.prod.yaml -f compose.http.yaml up -d --build
curl -sf http://your-host/healthz && echo OK
```

HTTP sends login credentials and financial data without transport encryption. Treat this as a
temporary or externally TLS-terminated mode and move to the base TLS configuration when possible.
The bundled nginx deliberately replaces (rather than appends) client-supplied `X-Forwarded-For`
to prevent rate-limit spoofing. If another trusted reverse proxy sits in front of the VM, configure
nginx `set_real_ip_from` for that proxy's exact address and `real_ip_header` before relying on the
forwarded client address; never trust this header from arbitrary sources.

## 3. Bootstrap the first admin

```bash
docker compose -f compose.prod.yaml exec api python -m app.scripts.bootstrap_admin
# -> creates the OWNER from HOMO_ADMIN_BOOTSTRAP_EMAIL/PASSWORD
# The command is idempotent and also verifies required system accounts/mappings.
```

Rotate a leaked or temporary password without placing it in command arguments, and revoke every
active refresh session for that user:

```bash
read -r -p 'User email: ' HOMO_ROTATE_USER_EMAIL
read -r -s -p 'New password: ' HOMO_ROTATE_USER_PASSWORD; echo
export HOMO_ROTATE_USER_EMAIL HOMO_ROTATE_USER_PASSWORD
docker compose -f compose.prod.yaml exec -T \
  -e HOMO_ROTATE_USER_EMAIL -e HOMO_ROTATE_USER_PASSWORD \
  api python -m app.scripts.rotate_password
unset HOMO_ROTATE_USER_EMAIL HOMO_ROTATE_USER_PASSWORD
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
| Uploads fail | verify the `media` volume and ownership: `docker compose -f compose.prod.yaml run --rm media-init` |
| 429 on login | rate limit — expected; check for brute-force attempts in logs |

## 7. Publishing images / CI deployment

The repository intentionally has no inactive or placeholder publish job. Add a reviewed registry
and deployment workflow only after credentials, environment protection, rollback, and explicit
owner authorization are available.

## 7b. CI/CD workflows (verified in slice 9 packaging)

- `ci.yml` — backend (ruff/mypy/pytest+coverage on PG16), frontend (eslint/tsc/vitest
  --coverage/build), and `contract-drift` (regenerates the OpenAPI client and fails on drift).
  Requires `@vitest/coverage-v8` (present) and the api-client `generate` script (simplified).
- `security.yml` — pip-audit on the lockfile (verified 0 findings), strict `npm audit`
  (0 vulnerabilities), trufflehog secret scan, CodeQL.
- `docker.yml` — builds api+web, boots the prod stack via `.github/compose.smoke.yaml`, verifies
  production bootstrap twice, and validates an HttpOnly cookie login against the real API
  (publishes :8000/:3000 for smoke tests; prod compose keeps ports nginx-only), scans both
  images with trivy (fails only on FIXABLE HIGH/CRITICAL via `ignore-unfixed`; documented
  accepts go in `.trivyignore`). Publishing/deployment is not present until the owner adds a
  protected environment and registry credentials.
- **Base images are pinned to digests** (python:3.12-slim, node:20-alpine in the Dockerfiles;
  postgres:16-alpine and nginx in compose.prod.yaml) for reproducible, supply-chain-safe
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
