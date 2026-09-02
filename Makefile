.PHONY: help start stop restart status logs health setup migrate lock-check format lint test test-cov compose-check build-check ci clean

help: ## Show Falco development commands
	@echo "Falco Agentic RAG commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

start: ## Start the Falco service stack
	docker compose up --build -d

stop: ## Stop the Falco service stack
	docker compose down

restart: ## Restart all services
	docker compose restart

status: ## Show service status
	docker compose ps

logs: ## Follow service logs
	docker compose logs -f

health: ## Fail unless the reference stack is ready
	@set -e; \
		echo "Checking Falco reference stack..."; \
		curl -fsS http://localhost:8000/api/v1/ready >/dev/null; echo "  Falco API: ready"; \
		curl -fsS http://localhost:9200/_cluster/health >/dev/null; echo "  OpenSearch: healthy"; \
		curl -fsS http://localhost:8080/health >/dev/null; echo "  Airflow: healthy"; \
		curl -fsS http://localhost:11434/api/version >/dev/null; echo "  Ollama: healthy"

setup: ## Install the exact locked local development environment
	uv sync --locked

migrate: ## Apply Falco PostgreSQL schema migrations
	uv run alembic upgrade head

lock-check: ## Verify uv.lock matches pyproject.toml without modifying it
	uv lock --check

format: ## Format code
	uv run ruff format .

lint: ## Run deterministic static checks without modifying source
	uv run ruff check .

test: ## Run the deterministic unit/API suite
	uv run pytest tests/unit tests/api

test-cov: ## Run unit/API tests with coverage
	uv run pytest tests/unit tests/api --cov=src --cov-report=html

compose-check: ## Validate the reference Compose configuration
	docker compose config --quiet

build-check: ## Build application and Airflow images
	docker build -t falco-agentic-rag:ci .
	docker build -t falco-airflow:ci ./airflow

ci: lock-check lint test compose-check build-check ## Run local release-quality checks

clean: ## Remove local containers and persistent volumes
	docker compose down -v
	docker system prune -f
