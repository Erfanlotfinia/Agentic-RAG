# Configuration

Falco reads application configuration from environment variables through Pydantic Settings. Docker Compose also consumes deployment-specific variables from the same `.env` file. Copy the example before a local deployment:

```bash
cp .env.example .env
```

## Host exposure

The reference Compose stack binds published ports to loopback by default:

```text
FALCO_BIND_ADDRESS=127.0.0.1
```

This keeps the API, administrative UIs, databases, Redis, OpenSearch, Ollama, and MinIO from being exposed on every host interface by accident. Change the bind address only when the host network and authenticated ingress are intentionally configured for remote access.

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

`POSTGRES_DATABASE_URL` points to the canonical Falco document database. The reference Compose stack uses `POSTGRES_PASSWORD` as the single password source for the PostgreSQL service and constructs the API/Airflow container connection URLs from that value. If you run Falco outside Compose, set `POSTGRES_DATABASE_URL` explicitly for that environment.

## arXiv source connector

`ARXIV__*` settings control the source API URL, category, result limits, download retries, PDF cache location, and concurrency.

The default reference deployment targets `cs.AI`; this is a deployment choice, not an architectural requirement.

## PDF parsing

`PDF_PARSER__*` controls page/file limits, OCR, and table-structure extraction.

## Chunking

`CHUNKING__*` controls chunk size, overlap, minimum chunk size, and section-aware splitting.

## OpenSearch and embeddings

`OPENSEARCH__*` controls the host, index naming, vector dimension, vector space, RRF search-pipeline name, and hybrid-search sizing.

`OPENSEARCH__VECTOR_DIMENSION` is passed to both the OpenSearch index mapping and Jina embedding requests, so those two sides stay aligned. Changing the vector dimension, embedding model, vector space, or existing index mapping requires a planned reindex; changing an environment value does not mutate an already-created index mapping in place.

`JINA_API_KEY` is required for vector/hybrid retrieval. If query embedding fails at runtime, Falco falls back to BM25. Passage embeddings are required when building a vector-enabled index.

## Ollama

```text
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_TIMEOUT=300
```

Ensure the configured model exists in Ollama before serving production traffic.

## Redis

`REDIS__*` controls host, port, authentication, database number, socket behavior, and TTL. The same TTL governs exact RAG cache entries and Agentic conversation history.

The reference Compose stack enables Redis authentication with `REDIS__PASSWORD`; the API receives the same value through `.env`. Falco versions Redis key namespaces so incompatible cache/session storage formats can be invalidated across upgrades without colliding with older keys.

## Langfuse

Client settings use `LANGFUSE__*` because they are consumed by Falco's Pydantic configuration. Self-hosted Langfuse service variables are separate Docker-service settings and intentionally use their server-specific names.

For the reference local stack:

```text
LANGFUSE_PUBLIC_URL=http://localhost:3001
LANGFUSE_MEDIA_PUBLIC_ENDPOINT=http://localhost:9090
```

`LANGFUSE_PUBLIC_URL` is the operator/browser-facing Langfuse URL and is used for `NEXTAUTH_URL`. `LANGFUSE_MEDIA_PUBLIC_ENDPOINT` must be reachable by browsers/SDK clients for signed media uploads. The Compose stack separately configures the internal MinIO endpoint as `http://langfuse-minio:9000` for container-to-container access.

The reference stack expects distinct secrets for the Langfuse application and its stateful dependencies, including:

```text
LANGFUSE_NEXTAUTH_SECRET=...
LANGFUSE_SALT=...
LANGFUSE_ENCRYPTION_KEY=...
LANGFUSE_REDIS_PASSWORD=...
LANGFUSE_POSTGRES_PASSWORD=...
LANGFUSE_CLICKHOUSE_PASSWORD=...
LANGFUSE_MINIO_ACCESS_KEY=...
LANGFUSE_MINIO_SECRET_KEY=...
LANGFUSE_INIT_USER_PASSWORD=...
```

The bootstrap configuration creates the Falco organization and configured admin user. It does not pretend that a project was created from a project name alone. Create a Langfuse project and its public/secret API keys, then set `LANGFUSE__PUBLIC_KEY`, `LANGFUSE__SECRET_KEY`, and `LANGFUSE__ENABLED=true` when tracing is ready to be enabled.

## Telegram

Telegram is optional and disabled by default. Enable it only after supplying a valid bot token:

```text
TELEGRAM__ENABLED=true
TELEGRAM__BOT_TOKEN=...
```

## Airflow

Falco currently pins Apache Airflow 2.10.3. Its webserver health endpoint is `http://localhost:8080/health`.

The entrypoint runs `airflow db migrate` before starting the services and creates or synchronizes the configured administrator account from explicit environment variables:

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
