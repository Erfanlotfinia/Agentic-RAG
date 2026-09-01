# Operations

This guide covers routine operations for a Falco Agentic RAG deployment.

## Health and readiness

```bash
curl http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/ready
make health
```

`/health` reports PostgreSQL, OpenSearch, and Ollama status for diagnostics. `/ready` uses the same required-dependency checks but returns HTTP 503 when core RAG serving is degraded; use it for readiness/load-balancer decisions.

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

## Reindexing

OpenSearch is a derived retrieval model. Canonical parsed paper data is retained in PostgreSQL, so retrieval chunks can be rebuilt from the canonical store when index configuration changes.

Before changing vector dimensions, embedding models, index mappings, vector space, or chunking rules, plan a complete reindex and validate storage capacity. Environment changes do not mutate an existing OpenSearch vector mapping in place.

## Cache and sessions

Redis entries expire according to `REDIS__TTL_HOURS`.

- Conventional RAG cache entries are safe to invalidate; they will be regenerated on demand.
- A hybrid request that temporarily degrades to BM25 is not retained as a valid hybrid cache entry.
- Agentic session history is stored as a bounded Redis list with atomic append/trim/expiry operations.
- Cache/session key namespaces are versioned so storage-format changes do not collide with older transient data.
- Clearing session keys removes conversational continuity but does not affect indexed knowledge.

Redis connectivity is lazy and fail-open. A Redis outage does not prevent the API from starting or serving uncached/stateless requests; after Redis recovers, subsequent cache/session operations can use the same client without an API restart.

## Backups

At minimum, back up:

- PostgreSQL canonical data;
- OpenSearch data or a proven reproducible reindex path;
- Langfuse data if trace history is operationally important;
- Airflow metadata/logs if workflow history must be retained;
- deployment environment/secrets through an approved secret-management system.

Redis is usually recoverable as ephemeral cache/session state, but include it if conversation continuity across a recovery event is a requirement.

The reference Compose topology currently shares the PostgreSQL database used by Falco canonical data with Airflow metadata. A hardened commercial deployment should separate those databases/credentials before relying on independent backup, restore, and migration boundaries.

## Dependency degradation

- Jina query-embedding failure: query-time hybrid retrieval falls back to BM25 and reports the effective mode.
- Langfuse disabled/unavailable: tracing and feedback are unavailable; core RAG remains usable.
- Redis unavailable: response caching and Agentic session persistence fail open; RAG requests can continue.
- OpenSearch unavailable: retrieval-dependent features are unavailable and readiness fails.
- Ollama unavailable: generation-dependent features are unavailable and readiness fails.

## Capacity signals

Monitor:

- OpenSearch index size and search latency;
- PostgreSQL storage growth;
- Airflow DAG duration/failures and missed schedules;
- Ollama generation latency and memory use;
- API latency/error rate and readiness failures;
- Redis memory/evictions;
- Langfuse storage growth;
- cached PDF storage and persistent Docker volumes.

## Recovery

For a destructive clean local reset:

```bash
docker compose down -v
```

This deletes persistent volumes and therefore should never be used as a production recovery procedure. Production recovery should restore stateful services from backups, verify Airflow metadata separately, and rebuild the OpenSearch retrieval model when required.
