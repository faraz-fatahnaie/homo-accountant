#!/usr/bin/env bash
# ============================================================
# Safe first-admin bootstrap.
# Creates the initial OWNER account from environment variables:
#   ARYA_ADMIN_BOOTSTRAP_EMAIL + ARYA_ADMIN_BOOTSTRAP_PASSWORD
# Refuses to run in a non-production API image unless forced.
# Run INSIDE the api container:
#   docker compose -f compose.prod.yaml exec api python -m app.scripts.bootstrap_admin
# ============================================================
set -euo pipefail
docker compose -f compose.prod.yaml exec api \
  python -m app.scripts.bootstrap_admin "$@"
