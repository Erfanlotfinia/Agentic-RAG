.PHONY: help start stop restart status logs health setup lock-check format lint test test-cov ci clean

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

setup: ## Install/update the local development environment
	uv sync

lock-check: ## Verify uv.lock matches pyproject.toml without modifying it
	uv lock --check

format: ## Format code
	uv run ruff format

lint: ## Lint and type check without modifying source
	uv run ruff check .
	uv run mypy src/

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html

ci: lock-check lint test ## Run local release-quality checks

clean: ## Remove local containers and persistent volumes
	docker compose down -v
	docker system prune -f
