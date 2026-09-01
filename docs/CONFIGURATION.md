# Configuration

Falco reads configuration from environment variables through Pydantic Settings. Copy `.env.example` to `.env` for a local deployment.

```bash
cp .env.example .env
```

## Application

```text
APP_VERSION=1.0.0
SERVICE_NAME=falco-agentic-rag-api
DEBUG=false
ENVIRONMENT=development
```

Set `ENVIRONMENT=production` and keep `DEBUG=false` for production deployments.

## Nested settings

Nested Pydantic settings use a double underscore delimiter. Examples:

```text
OPENSEARCH__HOST=http://opensearch:9200
REDIS__HOST=redis
LANGFUSE__HOST=http://langfuse-web:3000
TELEGRAM__ENABLED=false
```

Do not replace these with single-underscore variants unless the setting is defined at the top application level.

## PostgreSQL

`POSTGRES_DATABASE_URL` points to the canonical Falco document database. The application also supports pool-size and SQL logging settings through the top-level Settings model.

## arXiv source connector

`ARXIV__*` settings control the source API URL, category, result limits, download retries, PDF cache location, and concurrency.

The default reference deployment targets `cs.AI`; this is a deployment choice, not an architectural requirement.

## PDF parsing

`PDF_PARSER__*` controls page/file limits, OCR, and table-structure extraction.

## Chunking

`CHUNKING__*` controls chunk size, overlap, minimum chunk size, and section-aware splitting.

## OpenSearch

`OPENSEARCH__*` controls the host, index naming, vector dimension, vector space, RRF pipeline, and hybrid-search sizing.

The current Jina embedding configuration produces 1024-dimensional vectors, so changing embedding models may require an index mapping change and reindex.

## Jina embeddings

`JINA_API_KEY` is required for vector/hybrid retrieval. If query embedding fails at runtime, Falco falls back to BM25. Passage embeddings are still required when building a vector-enabled index.

## Ollama

```text
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_TIMEOUT=300
```

Ensure the configured model exists in Ollama before serving production traffic.

## Redis

`REDIS__*` controls host, port, authentication, database number, socket behavior, and TTL. The same TTL governs exact RAG cache entries and Agentic conversation history.

## Langfuse

Client settings use `LANGFUSE__*` because they are consumed by Falco's Pydantic configuration. Self-hosted Langfuse service variables such as `LANGFUSE_SALT` and `LANGFUSE_ENCRYPTION_KEY` are separate Docker-service settings and intentionally use their server-specific names.

Tracing should remain disabled until valid public/secret keys are configured.

## Telegram

Telegram is optional and disabled by default. Enable it only after supplying a valid bot token:

```text
TELEGRAM__ENABLED=true
TELEGRAM__BOT_TOKEN=...
```

## Airflow

Airflow 2.10.3 uses the standard webserver health endpoint at `http://localhost:8080/health`. The reference container creates the configured administrator account during startup from explicit environment variables:

```text
AIRFLOW_ADMIN_USERNAME=admin
AIRFLOW_ADMIN_FIRSTNAME=Falco
AIRFLOW_ADMIN_LASTNAME=Admin
AIRFLOW_ADMIN_EMAIL=admin@example.com
AIRFLOW_ADMIN_PASSWORD=change-me-strong-airflow-admin-password
```

The entrypoint refuses to start when these variables are missing. Replace the example password before starting any non-disposable deployment and restrict the Airflow UI to authorized operators.

## Secrets

The example environment file contains placeholders only. Generate unique values for all deployment secrets and never commit `.env`.

See [SECURITY.md](../SECURITY.md) before exposing any service outside a trusted local/private network.
