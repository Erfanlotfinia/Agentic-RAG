# Operations

This guide covers routine operations for a Falco Agentic RAG deployment.

## Health and readiness

```bash
curl http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/ready
make health
```

`/health` reports PostgreSQL, OpenSearch, and Ollama status for diagnostics. `/ready` uses the same required-dependency checks but returns HTTP 503 when core RAG serving is degraded; use it for readiness/load-balancer decisions. Both endpoints intentionally remain public even when built-in API authentication is enabled.

## Service status and logs

```bash
make status
make logs
```

Or use Docker Compose directly:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f airflow
```

## Database migrations

Canonical Falco schema changes are owned by Alembic. The reference stack applies migrations through the one-shot `migrate` service before API/Airflow startup.

Useful operator checks:

```bash
uv run alembic current
uv run alembic upgrade head
```

Back up the canonical database before production schema changes and test upgrades on staging/restored data first. Application startup does not create canonical tables automatically.

Airflow metadata lives in the separate `airflow_db` database under `airflow_user`; DAG application data continues to use canonical `rag_db`. The `airflow-db-init` one-shot service idempotently prepares/synchronizes the Airflow role/database before Airflow starts.

## Ingestion pipeline

The `arxiv_paper_ingestion` DAG runs daily at 06:00 UTC by default and targets the previous calendar date.

```text
setup_environment
      ↓
fetch_daily_papers
      ↓
index_papers_hybrid
      ↓
generate_daily_report
      ↓
cleanup_temp_files
```

Airflow is the operational interface for inspecting task runs, logs, retries, and XCom report data. The daily schedule prevents systematic weekday/weekend date gaps, but `catchup=false` means a multi-day scheduler outage still requires an explicit backfill/recovery procedure.

Falco paginates arXiv results up to `ARXIV__MAX_RESULTS`. With the default `ARXIV__FAIL_ON_TRUNCATION=true`, a day whose reported result count exceeds that cap fails before PDF download/parsing rather than silently ingesting a partial day. Treat this as an operational capacity signal: raise the cap deliberately or split/backfill the source window instead of disabling completeness checks without understanding the data-loss tradeoff.

PDF transfers are bounded by `PDF_PARSER__MAX_FILE_SIZE_MB`, use temporary `.part` files, and are atomically promoted only after a complete successful download. Failed/oversized partial files should not be treated as valid cache entries.

## Reindexing

OpenSearch is a derived retrieval model. Canonical parsed paper data is retained in PostgreSQL, so retrieval chunks can be rebuilt from the canonical store when index configuration changes.

Before changing vector dimensions, embedding models, index mappings, vector space, or chunking rules, plan a complete reindex and validate storage capacity. Environment changes do not mutate an existing OpenSearch vector mapping in place.

## Cache, sessions, and rate limiting

Redis entries expire according to `REDIS__TTL_HOURS` for cache/session data.

- Conventional RAG cache entries are safe to invalidate; they will be regenerated on demand.
- A hybrid request that temporarily degrades to BM25 is not retained as a valid hybrid cache entry.
- Agentic session history is stored as a bounded Redis list with atomic append/trim/expiry operations.
- Cache/session key namespaces are versioned so storage-format changes do not collide with older transient data.
- Clearing session keys removes conversational continuity but does not affect indexed knowledge.
- When `AUTH__RATE_LIMIT_ENABLED=true`, Redis also stores short-lived fixed-window API counters keyed by a hash of the authenticated API key.

Redis connectivity remains fail-open for ordinary cache/session features: a Redis outage does not prevent the API from starting or serving uncached/stateless requests. API rate limiting is deliberately different: when enabled, a Redis outage returns HTTP 503 for protected requests instead of silently bypassing the configured limit.

## Backups

At minimum, back up:

- PostgreSQL `rag_db` canonical data and Alembic version state;
- PostgreSQL `airflow_db` if workflow history/state must be retained;
- OpenSearch data or a proven reproducible reindex path;
- Langfuse data if trace history is operationally important;
- Airflow logs when required by operations/compliance;
- deployment environment/secrets through an approved secret-management system.

Redis is usually recoverable as ephemeral cache/session/rate-limit state, but include it if conversation continuity across a recovery event is a requirement.

## Dependency degradation

- Jina query-embedding failure: query-time hybrid retrieval falls back to BM25 and reports the effective mode.
- Langfuse disabled/unavailable: tracing and feedback are unavailable; core RAG remains usable.
- Redis unavailable with rate limiting disabled: response caching and Agentic session persistence fail open; RAG requests can continue.
- Redis unavailable with rate limiting enabled: authenticated protected API requests fail with HTTP 503 rather than bypassing the limit.
- OpenSearch unavailable: retrieval-dependent features are unavailable and readiness fails.
- Ollama unavailable: generation-dependent features are unavailable and readiness fails.

## Capacity signals

Monitor:

- OpenSearch index size and search latency;
- PostgreSQL canonical and Airflow metadata storage growth independently;
- Airflow DAG duration/failures, missed schedules, and ingestion truncation failures;
- Ollama generation latency and memory use;
- API latency/error rate, HTTP 401/429/503 rates, and readiness failures;
- Redis memory/evictions;
- Langfuse storage growth;
- cached PDF storage and persistent Docker volumes.

## Recovery

For a destructive clean local reset:

```bash
docker compose down -v
```

This deletes persistent volumes and therefore should never be used as a production recovery procedure. Production recovery should restore canonical and Airflow metadata databases according to their separate backup boundaries, re-apply/verify Alembic state, restore other required stateful services, and rebuild the OpenSearch retrieval model when required.
