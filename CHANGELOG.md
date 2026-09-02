# Changelog

All notable product changes to Falco Agentic RAG are documented here.

## Unreleased — 1.0.0 candidate

Candidate commercial product baseline. Rename this section to a released version/date only when the release is intentionally tagged/published. The repository includes permanent CI release gates for locked dependencies, Ruff, unit/API tests, Alembic migration round trips, Compose database bootstrap, and API/Airflow image builds.

### Platform

- Self-hosted FastAPI serving layer with diagnostic health, readiness, search, RAG, streaming RAG, Agentic RAG, and feedback endpoints.
- PostgreSQL `rag_db` canonical document storage and OpenSearch chunk-level retrieval model.
- Isolated PostgreSQL `airflow_db` metadata store with separate Airflow credentials.
- Alembic-owned canonical database schema with explicit pre-start migration service.
- Automated daily arXiv ingestion and indexing with Apache Airflow and Docling PDF parsing.
- Paginated arXiv discovery with a configurable completeness cap and strict fail-on-truncation behavior.
- Bounded, temporary-file, atomic PDF downloads before parsing.
- BM25 and native hybrid BM25/vector retrieval with Reciprocal Rank Fusion.
- Ollama local model generation and Jina query/passage embeddings with aligned configurable vector dimensions.
- Regenerated Falco 1.0 dependency lock with stale course-era notebook/Jupyter development dependencies removed.

### Agentic RAG

- LangGraph workflow with domain guardrails, retrieval, relevance grading, query rewriting, bounded retries, and grounded answer generation.
- Request-level model, retrieval mode, category, and top-k configuration.
- Actual source, chunks-used, effective-search-mode, retrieval-attempt, rewritten-query, and trace metadata in responses.
- Redis-backed cross-worker conversation sessions when a client supplies a persistent session ID.

### Reliability and operations

- BM25 query-time fallback when Jina query embeddings fail without poisoning the hybrid response cache.
- Versioned Redis cache/session namespaces and atomic bounded session-history writes.
- Lazy fail-open Redis connectivity for cache/session behavior that can recover without restarting the API.
- Native OpenSearch hybrid pagination, shared category filters, minimum-score handling, total-hit preservation, and configured search-pipeline lifecycle.
- OpenSearch username/password, TLS, certificate-verification, and CA-bundle client configuration.
- Separate diagnostic `/health` and HTTP-failing `/ready` probes.
- Daily ingestion scheduling to avoid systematic calendar-date gaps.
- Strict arXiv completeness failure before expensive PDF processing when the configured cap is insufficient.
- Airflow metadata database bootstrap designed to work for fresh installs and existing PostgreSQL volumes.
- Permanent GitHub Actions CI for lock validation, Ruff, unit/API tests, migration upgrade/downgrade/re-upgrade, Compose DB bootstrap, and API/Airflow image builds.

### Security and distribution

- Product branding as Falco Agentic RAG.
- Optional built-in Bearer API authentication with minimum key-length validation; health/readiness remain public probes.
- Optional Redis-backed authenticated API rate limiting with HTTP 429 headers and fail-closed behavior when the limiter is unavailable.
- Loopback-only host port publication by default in the reference Compose stack.
- Environment-driven deployment credentials and Airflow administrator bootstrap.
- Separate credentials/database for Airflow metadata versus canonical Falco documents.
- Non-root Falco API runtime container.
- Generic client-facing internal-error responses while preserving server-side diagnostics.
- Docker build-context exclusions for secrets, local data, and development artifacts.
- Product documentation for architecture, API, configuration, deployment, operations, and security.
- Temporary write-enabled lock/style repair workflows removed after generating the final branch state; permanent CI is read-only.
- Course-specific notebooks, week/module documentation, tutorial DAG artifacts, and legacy course visuals removed from the product tree.
- Upstream MIT provenance and required notice documented in `THIRD_PARTY_NOTICES.md`.
