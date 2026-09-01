.PHONY: help start stop restart status logs health setup format lint test test-cov clean

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

health: ## Check core service health
	@echo "Checking Falco service health..."
	@curl -s http://localhost:8000/api/v1/health | jq . || echo "Falco API not responding"
	@curl -s http://localhost:9200/_cluster/health | jq . || echo "OpenSearch not responding"
	@curl -s http://localhost:8080/api/v2/monitor/health || echo "Airflow not responding"
	@curl -s http://localhost:11434/api/version | jq . || echo "Ollama not responding"

setup: ## Install Python dependencies
	uv sync

format: ## Format code
	uv run ruff format

lint: ## Lint and type check
	uv run ruff check --fix
	uv run mypy src/

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html

clean: ## Remove local containers and persistent volumes
	docker compose down -v
	docker system prune -f
