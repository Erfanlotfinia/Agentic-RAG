# Architecture

Falco Agentic RAG is split into a knowledge pipeline and a serving platform. The separation keeps document processing asynchronous and makes query-time retrieval independent from the canonical document database.

## Knowledge pipeline

```text
arXiv API / PDFs
       │
       ▼
paginated ArxivClient + MetadataFetcher
       │
       ▼
bounded atomic PDF download
       │
       ▼
Docling PDF parsing
       │
       ▼
PostgreSQL rag_db
canonical document store
       │
       ▼
section-aware chunking
       │
       ▼
Jina passage embeddings
       │
       ▼
OpenSearch
chunks + metadata + vectors
```

The scheduled Airflow pipeline discovers papers, validates the configured arXiv completeness cap, parses source PDFs, writes canonical content to PostgreSQL, creates retrieval chunks, generates passage embeddings, and updates OpenSearch. With `ARXIV__FAIL_ON_TRUNCATION=true`, a source window that exceeds `ARXIV__MAX_RESULTS` fails before PDF processing rather than silently ingesting a partial set.

Airflow orchestration metadata is not stored in the canonical application database: the reference topology uses `airflow_db` / `airflow_user`, while DAG application data access continues to use `rag_db`.

## Serving platform

FastAPI exposes search, conventional RAG, streaming RAG, Agentic RAG, feedback, health, and readiness endpoints. Long-lived clients are initialized once during application startup and shared through `app.state`.

An optional request-security layer protects non-probe `/api/*` routes with Bearer authentication and optional Redis-backed rate limiting. Health and readiness are intentionally public infrastructure probes.

### Storage responsibilities

**PostgreSQL `rag_db`** is the canonical document store. It contains arXiv metadata, PDF URLs, parsed text, sections, references, parser metadata, processing state, and the Alembic schema version. Canonical schema changes are applied explicitly with Alembic before API startup.

**PostgreSQL `airflow_db`** is the isolated Airflow metadata store in the reference deployment. Separate credentials reduce coupling between orchestration metadata and canonical product data.

**OpenSearch** is the query-time retrieval model. Documents are denormalized chunks containing text, paper metadata, category information, section information, and configurable-dimension embeddings. It can be rebuilt from canonical data when index settings require a reindex.

**Redis** has three independent responsibilities: exact conventional-RAG response caching, bounded Agentic session history, and optional API rate-limit counters. Cache/session failures are fail-open for stateless serving; enabled API rate limiting is fail-closed if Redis is unavailable.

## Database lifecycle

Falco does not rely on application startup `create_all()` calls. Alembic owns the canonical PostgreSQL schema. The reference Compose stack runs a one-shot `migrate` service and blocks API/Airflow startup if `alembic upgrade head` fails.

A separate idempotent `airflow-db-init` service creates/synchronizes the Airflow role and metadata database on both fresh installations and upgrades before the Airflow entrypoint performs its own metadata migration.

## Retrieval

BM25 is a first-class retrieval mode. When a query embedding is available, Falco executes BM25 and kNN branches and combines their rankings with Reciprocal Rank Fusion through the configured OpenSearch search pipeline.

```text
text query ─────► BM25 ──┐
                         ├──► RRF ──► top-k chunks
query embedding ─► kNN ──┘
```

If the query-embedding call fails, the request degrades to BM25 rather than failing the complete retrieval flow, and response metadata reports the effective mode. Native hybrid pagination, category filters, score thresholds, and total-hit handling are applied consistently across the retrieval path.

## Agentic RAG

Falco uses one adaptive LangGraph workflow rather than an unbounded multi-agent system.

<p align="center">
  <img src="assets/agentic-workflow.png" alt="Falco Agentic workflow" width="850">
</p>

```text
START
  │
  ▼
Guardrail
  │
  ├── out of scope ──► OutOfScope ──► END
  │
  ▼
Retrieve
  │
  ▼
ToolNode(retrieve_papers)
  │
  ▼
Grade Documents
  │
  ├── relevant ─────► Generate Answer ──► END
  │
  └── not relevant
          │
          ▼
      Rewrite Query
          │
          └────────────► Retrieve
```

The workflow validates domain scope, retrieves paper chunks, grades retrieval quality, rewrites weak queries, retries retrieval up to a configured maximum, and produces a grounded answer from relevant context.

Request-level `model`, `top_k`, retrieval mode, categories, and optional session identifiers are applied to graph execution. The response reports the effective retrieval mode and actual retrieval metadata.

## Sessions

An explicit `session_id` enables bounded conversational history. Recent user/assistant turns are persisted in Redis and restored into subsequent graph invocations. This design is worker-safe across the four Uvicorn workers used by the default image.

Requests without `session_id` are isolated.

## Generation

Ollama provides the local generation layer. Conventional and Agentic RAG both ground generation on OpenSearch retrieval results. Agentic answer generation is additionally gated by relevance grading and bounded query rewriting.

## Observability

Langfuse 3.x captures root RAG/Agentic requests and major graph operations when explicitly enabled with valid project credentials. Trace metadata includes retrieval and generation context where available. Feedback can be attached to a trace through the feedback endpoint.

## Optional interfaces

The HTTP API is the primary integration surface. Falco also includes:

- a Gradio-based Research Console for local interactive use, including optional forwarding of the Falco API key;
- an optional Telegram bot backed by the same application-scoped Agentic RAG service.
