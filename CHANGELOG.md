# Changelog

All notable product changes to Falco Agentic RAG are documented here.

## Unreleased — 1.0.0 candidate

Candidate commercial product baseline. Rename this section to the release version/date only after the lockfile, automated tests, image build, and deployment smoke checks have passed and the release is actually tagged.

### Platform

- Self-hosted FastAPI serving layer with diagnostic health, readiness, search, RAG, streaming RAG, Agentic RAG, and feedback endpoints.
- PostgreSQL canonical document storage and OpenSearch chunk-level retrieval model.
- Automated daily arXiv ingestion and indexing with Apache Airflow and Docling PDF parsing.
- BM25 and native hybrid BM25/vector retrieval with Reciprocal Rank Fusion.
- Ollama local model generation and Jina query/passage embeddings with aligned configurable vector dimensions.

### Agentic RAG

- LangGraph workflow with domain guardrails, retrieval, relevance grading, query rewriting, bounded retries, and grounded answer generation.
- Request-level model, retrieval mode, category, and top-k configuration.
- Actual source, chunks-used, effective-search-mode, retrieval-attempt, rewritten-query, and trace metadata in responses.
- Redis-backed cross-worker conversation sessions when a client supplies a persistent session ID.

### Reliability and operations

- BM25 query-time fallback when Jina query embeddings fail without poisoning the hybrid response cache.
- Versioned Redis cache/session namespaces and atomic bounded session-history writes.
- Lazy fail-open Redis connectivity that can recover without restarting the API.
- Native OpenSearch hybrid pagination, shared category filters, minimum-score handling, total-hit preservation, and configured search-pipeline lifecycle.
- Separate diagnostic `/health` and HTTP-failing `/ready` probes.
- Daily ingestion scheduling to avoid systematic calendar-date gaps.
- Airflow metadata migration/bootstrap aligned with the pinned Airflow 2.10 runtime.

### Security and distribution

- Product branding as Falco Agentic RAG.
- Loopback-only host port publication by default in the reference Compose stack.
- Environment-driven deployment credentials and Airflow administrator bootstrap.
- Non-root Falco API runtime container.
- Generic client-facing internal-error responses while preserving server-side diagnostics.
- Docker build-context exclusions for secrets, local data, and development artifacts.
- Product documentation for architecture, API, configuration, deployment, operations, and security.
- Course-specific notebooks, week/module documentation, tutorial DAG artifacts, and legacy course visuals removed from the product tree.
- Upstream MIT provenance and required notice documented in `THIRD_PARTY_NOTICES.md`.
