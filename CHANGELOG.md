# Changelog

All notable product changes to Falco Agentic RAG are documented here.

## 1.0.0 — 2026-09-01

Initial commercial product baseline.

### Platform

- Self-hosted FastAPI serving layer with health, search, RAG, streaming RAG, Agentic RAG, and feedback endpoints.
- PostgreSQL canonical document storage and OpenSearch chunk-level retrieval model.
- Automated arXiv ingestion and indexing with Apache Airflow and Docling PDF parsing.
- BM25 and hybrid BM25/vector retrieval with Reciprocal Rank Fusion.
- Ollama local model generation and Jina query/passage embeddings.

### Agentic RAG

- LangGraph workflow with domain guardrails, retrieval, relevance grading, query rewriting, bounded retries, and grounded answer generation.
- Request-level model, retrieval mode, category, and top-k configuration.
- Actual source, chunks-used, effective-search-mode, retrieval-attempt, and trace metadata in responses.
- Redis-backed cross-worker conversation sessions.

### Reliability and observability

- BM25 query-time fallback when Jina query embeddings fail.
- Redis exact-response caching.
- Langfuse 3.x tracing and feedback support.
- Shared application-scoped Agentic service for HTTP and Telegram interfaces.

### Distribution

- Product branding as Falco Agentic RAG.
- Product documentation for architecture, API, configuration, deployment, operations, and security.
- Course-specific notebooks, week/module documentation, and tutorial DAG artifacts removed from the product tree.
