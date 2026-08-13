# ============================================================
# Homo Accountant — developer commands (source of truth; see AGENTS.md)
# ============================================================
SHELL := /bin/bash
API := apps/api
WEB := apps/web
COMPOSE_DEV := docker compose -f compose.yaml
COMPOSE_PROD := docker compose -f compose.prod.yaml

.PHONY: help db-up db-down dev api web migrate seed test lint format typecheck build e2e quality backup restore clean

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

# ---------- local environment ----------
db-up: ## start PostgreSQL + MinIO via docker compose
	$(COMPOSE_DEV) up -d db minio

db-down: ## stop the local stack
	$(COMPOSE_DEV) down

dev: ## run the full dev stack (db, minio, api, web)
	$(COMPOSE_DEV) up --build

api: ## run the API locally (expects db on localhost)
	cd $(API) && HOMO_DATABASE_URL="$${HOMO_DATABASE_URL:-postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_dev}" \
	  alembic upgrade head && HOMO_SEED_DEMO_USERS=true uvicorn app.main:app --reload --port 8000

web: ## run the web app locally
	cd $(WEB) && npm run dev

migrate: ## apply migrations
	cd $(API) && alembic upgrade head

seed: ## seed demo users (dev only)
	cd $(API) && HOMO_SEED_DEMO_USERS=true python -c "from app.core.db import SessionLocal; from app.domains.identity.seed import seed_demo_users; db=SessionLocal(); print('seeded:', seed_demo_users(db)); db.close()"

# ---------- quality gates ----------
format: ## format backend + frontend
	cd $(API) && ruff format app/ tests/ migrations/env.py
	cd $(WEB) && npx eslint . --fix

lint: ## lint backend + frontend
	cd $(API) && ruff check app/ tests/ migrations/env.py
	cd $(WEB) && npx eslint .

typecheck: ## strict type checks
	cd $(API) && mypy app/
	cd $(WEB) && npx tsc --noEmit

test: ## backend + frontend unit/component tests
	cd $(API) && HOMO_DATABASE_URL="$${TEST_DATABASE_URL:-postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_test}" python -m pytest tests/ --cov=app --cov-report=term-missing
	cd $(WEB) && npx vitest run

test-api: ## backend tests only
	cd $(API) && HOMO_DATABASE_URL="$${TEST_DATABASE_URL:-postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_test}" python -m pytest tests/ --cov=app

test-web: ## frontend tests only
	cd $(WEB) && npx vitest run

e2e: ## Playwright end-to-end (requires compose stack running: make dev)
	cd tests/e2e && npx playwright test

build: ## production builds
	cd $(WEB) && npm run build

quality: format lint typecheck test build ## all local gates

backup: ## database + storage backup
	./infra/backup/backup.sh

restore: ## restore a backup (usage: make restore DUMP=path)
	./infra/backup/restore.sh $(DUMP)

clean: ## remove generated artifacts
	rm -rf $(WEB)/.next $(WEB)/coverage test-results playwright-report
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
