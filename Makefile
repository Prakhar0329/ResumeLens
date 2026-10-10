# ResumeLens developer commands (macOS/Linux; Windows users see README "Installation").
# Usage: make setup && make backend   (and in a second terminal) make frontend

SHELL := /bin/bash
PYTHON ?= python3.11
VENV := backend/.venv
PY := $(VENV)/bin/python
PAIRS ?= evaluation/pairs.csv

.PHONY: help setup backend frontend test lint eval docker-up docker-down clean

help: ## List targets
	@grep -E "^[a-z-]+:.*## " $(MAKEFILE_LIST) | awk -F":.*## " "{printf \"  %-12s %s\\n\", \$$1, \$$2}"

setup: ## Create the venv, install all dependencies, copy env files
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	@if [ "$$(uname -s)" = "Linux" ]; then \
		$(PY) -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu; fi
	$(PY) -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	$(PY) -m spacy download en_core_web_sm
	@[ -f backend/.env ] || cp backend/.env.example backend/.env
	cd frontend && npm ci
	@[ -f frontend/.env.local ] || cp frontend/.env.local.example frontend/.env.local

backend: ## Run the API with auto-reload on :8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend: ## Run the Next.js dev server on :3000
	cd frontend && npm run dev

test: ## Backend tests with coverage, then frontend tests
	cd backend && .venv/bin/python -m pytest --cov=app/services --cov-report=term-missing
	cd frontend && npm run test

lint: ## Ruff, ESLint, TypeScript and Prettier checks
	cd backend && .venv/bin/ruff check app tests evaluation && .venv/bin/ruff format --check app tests evaluation
	cd frontend && npm run lint && npm run typecheck && npm run format:check

eval: ## Evaluate against labelled pairs (PAIRS=evaluation/pairs.csv; add ARGS=--tune)
	cd backend && .venv/bin/python evaluation/evaluate.py --pairs $(PAIRS) $(ARGS)

docker-up: ## Build and start both services
	docker compose up --build -d
	@echo "Frontend: http://localhost:3000   API docs: http://localhost:8000/docs"

docker-down: ## Stop the services (the database volume is kept)
	docker compose down

clean: ## Remove caches and build output (keeps the venv, node_modules and database)
	find backend -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
	rm -rf backend/.coverage backend/htmlcov frontend/.next frontend/coverage frontend/tsconfig.tsbuildinfo
