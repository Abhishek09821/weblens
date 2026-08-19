.DEFAULT_GOAL := help
SHELL := /bin/bash

# Playwright does not yet support Python 3.14; pin the interpreter used to build the venv.
PYTHON ?= python3.12
VENV := backend/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000

.PHONY: help setup setup-backend setup-frontend dev-backend dev-frontend \
        check check-backend check-frontend lint types test test-live \
        test-backend test-frontend contracts clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: setup-backend setup-frontend ## Install everything (downloads Chromium, ~150 MB)

setup-backend: ## Create the backend venv and install deps + Chromium
	@command -v $(PYTHON) >/dev/null || { echo "error: $(PYTHON) not found (Python 3.12 required)"; exit 1; }
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "backend[dev]"
	$(PY) -m playwright install chromium

setup-frontend: ## Install frontend deps
	cd frontend && npm install

dev-backend: ## Run the API with reload on 127.0.0.1:8000
	$(VENV)/bin/uvicorn weblens.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

dev-frontend: ## Run the Vite dev server on 127.0.0.1:5173
	cd frontend && npm run dev

check: check-backend check-frontend ## Lint, type-check and test both apps (offline)

check-backend: ## ruff + mypy + pytest (offline tiers only)
	$(VENV)/bin/ruff check backend
	$(VENV)/bin/ruff format --check backend
	$(VENV)/bin/mypy backend/src/weblens
	$(VENV)/bin/pytest backend -q -m "not live"

check-frontend: ## tsc + eslint + vitest
	cd frontend && npm run typecheck && npm run lint && npm run test -- --run

test: test-backend test-frontend ## Run both test suites (offline)

test-backend: ## Backend tests, offline tiers only
	$(VENV)/bin/pytest backend -q -m "not live"

test-frontend: ## Frontend tests, single run
	cd frontend && npm run test -- --run

test-live: ## Opt-in network tests against real websites
	WEBLENS_LIVE=1 $(VENV)/bin/pytest backend -q -m live

contracts: ## Regenerate contracts/openapi.json and the frontend types derived from it
	$(PY) backend/scripts/export_openapi.py --out contracts/openapi.json
	cd frontend && npm run gen:api

clean: ## Remove build and cache artifacts (keeps the venv and node_modules)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
	rm -rf frontend/dist frontend/coverage
