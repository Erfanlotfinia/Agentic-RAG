# Operations

This guide covers routine operations for a Falco Agentic RAG deployment.

## Health

```bash
curl http://localhost:8000/api/v1/health
make health
```

The API health endpoint checks PostgreSQL, OpenSearch, and Ollama and reports an overall `ok` or degraded state.

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

The `arxiv_paper_ingestion` DAG runs Monday-Friday at 06:00 UTC by default.

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

Airflow is the operational interface for inspecting task runs, logs, retries, and XCom report data.

## Reindexing

OpenSearch is a derived retrieval model. Canonical parsed paper data is retained in PostgreSQL, so retrieval chunks can be rebuilt from the canonical store when index configuration changes.

Before changing vector dimensions, embedding models, index mappings, or chunking rules, plan a complete reindex and validate storage capacity.

## Cache and sessions

Redis entries expire according to `REDIS__TTL_HOURS`.

- Conventional RAG cache entries are safe to invalidate; they will be regenerated on demand.
- Agentic session entries contain recent user/assistant conversation turns. Clearing them removes conversational continuity but does not affect indexed knowledge.

## Backups

At minimum, back up:

- PostgreSQL data volume/database;
- OpenSearch data or a reproducible reindex path;
- Langfuse data if trace history is operationally important;
- Airflow metadata/logs if workflow history must be retained;
- deployment environment/secrets through an approved secret-management system.

Redis is usually recoverable as ephemeral cache/session state, but include it if conversation continuity across a recovery event is a requirement.

## Dependency degradation

- Jina query-embedding failure: query-time retrieval falls back to BM25.
- Langfuse disabled/unavailable: tracing and feedback are unavailable, core RAG remains usable.
- Redis unavailable: cache/session behavior degrades; requests can still execute without persisted history when fail-open paths are used.
- OpenSearch unavailable: retrieval-dependent features are unavailable.
- Ollama unavailable: generation-dependent features are unavailable.

## Capacity signals

Monitor:

- OpenSearch index size and search latency;
- PostgreSQL storage growth;
- Airflow DAG duration/failures;
- Ollama generation latency and memory use;
- API latency/error rate;
- Redis memory/evictions;
- Langfuse storage growth;
- disk space used by cached PDFs and persistent Docker volumes.

## Recovery

For a clean local reset:

```bash
docker compose down -v
```

This deletes persistent volumes and therefore should never be used as a production recovery procedure. Production recovery should restore stateful services from backups and then rebuild the OpenSearch retrieval model if necessary.
