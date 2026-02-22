# ===========================================
# Makefile — Wiii Service
# Local dev shortcuts
# ===========================================

.PHONY: test test-fast test-cov lint format build up down logs migrate clean help

# ---- Testing ----

test: ## Run all unit tests
	PYTHONIOENCODING=utf-8 pytest tests/unit/ -v -p no:capture --tb=short

test-fast: ## Run tests, stop on first failure
	PYTHONIOENCODING=utf-8 pytest tests/unit/ -x -p no:capture --tb=short -q

test-cov: ## Run tests with coverage report
	PYTHONIOENCODING=utf-8 pytest tests/unit/ -p no:capture --tb=short --cov=app --cov-report=html --cov-report=term

# ---- Code Quality ----

lint: ## Run ruff linter
	ruff check app/

format: ## Auto-fix lint issues
	ruff check app/ --fix

# ---- Docker ----

build: ## Build Docker image
	docker build -t wiii-service:dev .

up: ## Start all services (docker compose)
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail service logs
	docker compose logs -f app

# ---- Database ----

migrate: ## Run Alembic migrations
	alembic upgrade head

# ---- Cleanup ----

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info/

# ---- Help ----

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
