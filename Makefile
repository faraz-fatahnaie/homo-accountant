# ============================================================
# Homo Accountant — developer commands (cross-platform)
#
# Auto-detects the OS so the same targets work on:
#   - Linux/macOS (bash)              e.g. `make dev`
#   - Windows: cmd, PowerShell 7+ or Git Bash
#
# Requirements:
#   - docker compose v2 (Docker Desktop on Windows — enable the WSL 2 engine)
#   - make (Windows: `choco install make`, or use WSL2 Ubuntu `apt install make`)
#   - python/node only for NON-docker targets (setup/test/format/...)
#
# Design notes:
#   - We do NOT force `SHELL := /bin/bash` — that is what made recipes fail
#     when make ran on Windows cmd. Recipes are written shell-agnostic.
#   - Python targets use the project venv automatically (no manual activate);
#     env vars are exported per-target so no `VAR=x cmd` / `set VAR=` syntax
#     (which differs between cmd and bash) appears in recipes.
#   - `make dev` is a single `docker compose ... up --build` line, so it works
#     identically on every OS and shell.
# ============================================================

# ---- OS detection (cmd and Git Bash both set OS=Windows_NT) ----
ifeq ($(OS),Windows_NT)
  IS_WINDOWS := 1
else
  IS_WINDOWS := 0
endif

# ---- toolchain (venv-aware) ----
API := apps/api
WEB := apps/web
COMPOSE_DEV := docker compose -f compose.yaml
COMPOSE_PROD := docker compose -f compose.prod.yaml
API_TEST_URL := postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_test

ifeq ($(IS_WINDOWS),1)
  VENV_PY := apps/api/.venv/Scripts/python.exe
  PY_IN_API := .venv/Scripts/python.exe
  FALLBACK_PY := python
else
  VENV_PY := apps/api/.venv/bin/python
  PY_IN_API := .venv/bin/python
  FALLBACK_PY := python3
endif

# python used from the repo root (prefer venv, else system)
PY := $(if $(wildcard $(VENV_PY)),$(VENV_PY),$(FALLBACK_PY))

.PHONY: help setup db-up db-down dev api web migrate seed test-db-create test test-api test-web lint format typecheck build e2e quality backup restore clean

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

# ---------- environment ----------
setup: ## create .venv + install backend deps + frontend deps
	cd $(API) && $(FALLBACK_PY) -m venv .venv
	cd $(API) && $(PY_IN_API) -m pip install -r requirements.txt -r requirements-dev.txt
	cd $(WEB) && npm ci

db-up: ## start PostgreSQL + MinIO via docker compose
	$(COMPOSE_DEV) up -d db minio

db-down: ## stop the dev stack
	$(COMPOSE_DEV) down

test-db-create: ## create the arya_test database (run once after db-up)
	$(COMPOSE_DEV) exec -T db psql -U arya -d postgres -c "CREATE DATABASE arya_test" || true

dev: ## run the full dev stack (db, minio, api, web) — Docker, any OS
	$(COMPOSE_DEV) up --build

api: export HOMO_DATABASE_URL ?= postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_dev
api: export HOMO_SEED_DEMO_USERS := true
api: ## run the API natively (expects db on localhost)
	cd $(API) && $(PY_IN_API) -m alembic upgrade head && $(PY_IN_API) -m uvicorn app.main:app --reload --port 8000

web: ## run the web app natively
	cd $(WEB) && npm run dev

migrate: ## apply migrations
	cd $(API) && $(PY_IN_API) -m alembic upgrade head

seed: export HOMO_SEED_DEMO_USERS := true
seed: ## seed demo users (dev only)
	cd $(API) && $(PY_IN_API) -c "from app.core.db import SessionLocal; from app.domains.identity.seed import seed_dev_data; db=SessionLocal(); print('seeded:', seed_dev_data(db)); db.close()"

# ---------- quality gates ----------
format: ## format backend + frontend
	cd $(API) && $(PY_IN_API) -m ruff format app/ tests/ migrations/env.py
	cd $(WEB) && npx eslint . --fix

lint: ## lint backend + frontend
	cd $(API) && $(PY_IN_API) -m ruff check app/ tests/ migrations/env.py
	cd $(WEB) && npx eslint .

typecheck: ## strict type checks
	cd $(API) && $(PY_IN_API) -m mypy app/
	cd $(WEB) && npx tsc --noEmit

test: export HOMO_DATABASE_URL ?= $(API_TEST_URL)
test: ## backend + frontend unit/component tests
	cd $(API) && $(PY_IN_API) -m pytest tests/ --cov=app --cov-report=term-missing
	cd $(WEB) && npx vitest run

test-api: export HOMO_DATABASE_URL ?= $(API_TEST_URL)
test-api: ## backend tests only
	cd $(API) && $(PY_IN_API) -m pytest tests/ --cov=app

test-web: ## frontend tests only
	cd $(WEB) && npx vitest run

e2e: ## Playwright end-to-end (requires compose stack running: make dev)
	cd tests/e2e && npx playwright test

build: ## production build (web)
	cd $(WEB) && npm run build

quality: format lint typecheck test build ## all local gates

# ---------- ops (require bash — Git Bash or WSL on Windows) ----------
backup: ## database + storage backup (bash)
	bash infra/backup/backup.sh

restore: ## restore a backup (usage: make restore DUMP=path) (bash)
	bash infra/backup/restore.sh $(DUMP)

clean: ## remove generated artifacts
	rm -rf $(WEB)/.next $(WEB)/coverage test-results playwright-report
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
