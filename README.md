# Falco Agentic RAG

<div align="center">
  <p><strong>Self-hosted research intelligence for technical teams.</strong></p>
  <p>Automated ingestion, hybrid retrieval, adaptive Agentic RAG, local LLM inference, observability, and multi-channel access in one deployable stack.</p>

  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/OpenSearch-2.19-orange.svg" alt="OpenSearch">
  <img src="https://img.shields.io/badge/LangGraph-Agentic_RAG-purple.svg" alt="LangGraph">
  <img src="https://img.shields.io/badge/Deployment-Self--Hosted-blue.svg" alt="Self Hosted">
</div>

## Product overview

**Falco Agentic RAG** is a deployable research-intelligence platform for teams that need grounded answers from an indexed technical knowledge base. The included reference deployment is optimized for arXiv computer-science research, while the architecture keeps ingestion, retrieval, generation, state, security controls, and observability modular.

Falco combines two paths:

- **Knowledge pipeline:** arXiv → PDF parsing → PostgreSQL → chunking → embeddings → OpenSearch.
- **Serving platform:** FastAPI → search / conventional RAG / streaming RAG / Agentic RAG → OpenSearch + Ollama, with Redis and Langfuse around the request flow.

PostgreSQL `rag_db` is the canonical document store. A separate PostgreSQL `airflow_db` stores Airflow metadata. OpenSearch is the derived retrieval model. Ollama provides local inference. Jina provides retrieval embeddings. Airflow automates ingestion. Redis provides response caching, optional Agentic session history, and optional API rate-limit counters. Langfuse provides optional tracing and feedback.

## Core capabilities

| Capability | What Falco provides |
|---|---|
| Automated ingestion | Scheduled paginated arXiv discovery, bounded/atomic PDF download, Docling parsing, persistence, and indexing |
| Ingestion completeness | Visible failure when an arXiv day exceeds the configured result cap instead of silently sampling a partial day |
| Hybrid retrieval | BM25 + vector retrieval with Reciprocal Rank Fusion, pagination, score thresholds, and category filters |
| Agentic RAG | Guardrails, retrieval, document grading, query rewriting, bounded retries, and grounded generation |
| Graceful degradation | Automatic BM25 fallback when query embeddings are unavailable; Redis cache/session failures do not block stateless serving |
| Conversation sessions | Redis-backed bounded Agentic history for explicit client session IDs, shared across API workers |
| API protection | Optional Bearer authentication plus Redis-backed rate limiting with public health/readiness probes |
| Database lifecycle | Alembic-owned canonical schema plus isolated Airflow metadata database/credentials |
| Local inference | Ollama-backed generation without sending prompts to a hosted LLM provider |
| Observability | Optional Langfuse traces for RAG/graph execution plus feedback capture |
| Multi-channel access | REST API, streaming API, Falco Research Console, and optional Telegram interface |
| Orchestration | Docker Compose reference stack and scheduled Airflow ingestion |

## Architecture

```text
                              KNOWLEDGE PIPELINE

      arXiv API / PDFs
             │
             ▼
   ArxivClient + MetadataFetcher
             │
             ▼
      PDFParser / Docling
             │
             ▼
       PostgreSQL 16
      canonical rag_db
             │
             ▼
        TextChunker
             │
             ▼
 Jina retrieval.passage embeddings
             │
             ▼
        OpenSearch 2.19
 chunk text + metadata + vectors
             │
────────────────────────────────────────────────────────────────
                              SERVING PLATFORM
             │
             ▼
           FastAPI
     ┌───────┼──────────────┐
     │       │              │
     ▼       ▼              ▼
 Search   Fast RAG      Agentic RAG
     │       │              │
     │    Redis cache     LangGraph
     │                      │
     │                optional Redis session
     │                      │
     └──────────────► OpenSearch
                         │
                  BM25 / kNN / RRF
                         │
                         ▼
                       Ollama
                         │
                         ▼
                      Response
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for storage ownership, retrieval behavior, and service boundaries.

## Agentic workflow

Falco uses one adaptive and bounded LangGraph workflow rather than an open-ended multi-agent loop.

<p align="center">
  <img src="docs/assets/agentic-workflow.png" alt="Falco Agentic RAG Workflow" width="850">
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

Request-level `model`, `top_k`, retrieval mode, categories, and optional `session_id` are applied to graph execution. Responses expose the effective search mode, actual source URLs, chunks used, retrieval attempts, rewritten-query metadata when applicable, trace ID when available, and a compact reasoning summary.

## Quick start

### Requirements

- Docker with Docker Compose
- Python 3.12 for local development
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Jina API key for hybrid/vector retrieval
- an Ollama model available to the Ollama service
- optional Langfuse project credentials
- optional Telegram bot token

### Start Falco

```bash
cp .env.example .env
# Configure required keys and replace all change-me values before deployment.

uv sync --locked
docker compose up --build -d
curl http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/ready
```

The reference Compose stack publishes host ports on `127.0.0.1` by default through `FALCO_BIND_ADDRESS`, reducing accidental network exposure. It also runs Alembic migrations before API startup and isolates Airflow metadata in `airflow_db`. For remotely reachable API traffic, enable `AUTH__ENABLED=true`, configure a strong `AUTH__API_KEY`, use TLS, and apply the network/identity controls described in [`SECURITY.md`](SECURITY.md).

Interactive API documentation is available at `http://localhost:8000/docs`.

### Falco Research Console

```bash
uv run python gradio_launcher.py
```

The local console is available at `http://localhost:7861`. When built-in API authentication is enabled, set `FALCO_API_KEY` so the console can authenticate to the Falco API.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Diagnostic platform and dependency status; public probe |
| GET | `/api/v1/ready` | Readiness probe; public, HTTP 503 when required RAG dependencies are degraded |
| POST | `/api/v1/hybrid-search/` | BM25 or hybrid chunk retrieval |
| POST | `/api/v1/ask` | Conventional grounded RAG |
| POST | `/api/v1/stream` | Streaming conventional RAG |
| POST | `/api/v1/ask-agentic` | Adaptive Agentic RAG |
| POST | `/api/v1/feedback` | Attach feedback to a Langfuse trace |

When `AUTH__ENABLED=true`, non-probe `/api/*` calls require `Authorization: Bearer <AUTH__API_KEY>`. Optional Redis-backed rate limiting returns standard limit/reset headers and HTTP 429 when exceeded.

Example Agentic request:

```json
{
  "query": "How does retrieval augmented generation reduce hallucination?",
  "top_k": 5,
  "use_hybrid": true,
  "model": "llama3.2:1b",
  "categories": ["cs.AI", "cs.CL"],
  "session_id": "research-session-42"
}
```

See [`docs/API.md`](docs/API.md) for integration details.

## Retrieval behavior

BM25 remains a first-class retrieval path. When a query embedding is available, Falco executes keyword and vector branches and fuses their rankings using Reciprocal Rank Fusion. Category filters apply across the hybrid query and pagination uses OpenSearch hybrid pagination depth. `latest_papers=true` intentionally uses date-sorted BM25 instead of mixing newest-first ordering with relevance fusion.

If query embedding fails, retrieval falls back to BM25 instead of failing the request and the effective response mode is reported as `bm25`.

```text
text query ─────► BM25 ──┐
                         ├──► RRF ──► top-k chunks
query embedding ─► kNN ──┘
```

## Cache and conversation state

Redis serves several independent responsibilities:

- **Exact response cache** for conventional RAG. Cache identity includes query, model, `top_k`, requested retrieval mode, and categories. A hybrid request that temporarily degrades to BM25 is not stored as a valid hybrid cache result.
- **Agentic session history** for explicit `session_id` values. Recent user/assistant turns are appended atomically, bounded, versioned by storage namespace, and expire using the configured Redis TTL.
- **Optional API rate-limit counters** when built-in authentication/rate limiting is enabled.

Requests without a `session_id` are isolated and do not expose Falco's internal graph thread identifier as a reusable public session. Redis-backed history is shared across the four Uvicorn workers used by the default Docker image.

Redis connectivity is lazy/fail-open for cache/session behavior: cache or session failures do not prevent normal stateless requests, and recovered Redis connectivity can be used by later requests without restarting the API. Rate limiting is intentionally fail-closed when enabled: protected API calls return HTTP 503 if the limiter cannot reach Redis.

## Observability

Falco targets Langfuse 3.x. Major RAG and graph operations can be traced, including guardrails, retrieval, grading, rewriting, and generation. Tracing is disabled by default until a real Langfuse project and public/secret keys are configured.

The self-hosted reference stack bootstraps the Falco organization/admin user but does not claim to create a project from a name alone. Public Langfuse and media URLs are configurable separately from container-internal MinIO access.

## Ingestion automation

The `arxiv_paper_ingestion` Airflow DAG runs daily at 06:00 UTC by default and targets the previous calendar date:

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

arXiv discovery is paginated up to `ARXIV__MAX_RESULTS`. With the default `ARXIV__FAIL_ON_TRUNCATION=true`, Falco fails before PDF download/parsing when arXiv reports more matches than the configured cap, preventing a partial day from being silently treated as complete. PDF downloads are size-bounded, written as temporary `.part` files, and atomically promoted after success.

The daily schedule prevents systematic Friday/weekend target-date gaps. Because `catchup=false`, a multi-day Airflow outage still requires an explicit backfill/checkpoint procedure.

See [`airflow/README.md`](airflow/README.md) for pipeline operations.

## Service endpoints

All reference Compose host bindings default to loopback.

| Service | Default local endpoint |
|---|---|
| Falco API / Swagger | `http://localhost:8000/docs` |
| Falco Research Console | `http://localhost:7861` |
| OpenSearch | `http://localhost:9200` |
| OpenSearch Dashboards | `http://localhost:5601` |
| Airflow | `http://localhost:8080` |
| Ollama | `http://localhost:11434` |
| Langfuse | `http://localhost:3001` |
| Redis | `localhost:6379` |
| PostgreSQL | `localhost:5432` |

## Product documentation

- [`docs/README.md`](docs/README.md) — documentation index
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components, data flow, storage, and Agentic graph
- [`docs/API.md`](docs/API.md) — API behavior, authentication, rate limiting, and request examples
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — environment and service configuration
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — deployment, migrations, topology, and production checklist
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — health, ingestion, migrations, recovery, and backups
- [`SECURITY.md`](SECURITY.md) — deployment security requirements
- [`CHANGELOG.md`](CHANGELOG.md) — candidate/release change history
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — upstream licensing notices

## Repository structure

```text
.
├── src/                         # Falco application code
│   ├── main.py                  # FastAPI composition root
│   ├── security.py              # optional API auth/rate limiting
│   ├── routers/                 # HTTP API
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic contracts
│   └── services/                # retrieval, agents, LLM, cache, tracing, integrations
├── alembic/                     # canonical PostgreSQL migrations
├── airflow/                     # scheduled ingestion pipeline
├── docs/                        # product documentation and architecture assets
├── tests/                       # automated test suite
├── .github/workflows/ci.yml     # locked/static/test/migration/container release gates
├── compose.yml                  # self-hosted reference stack
└── gradio_launcher.py           # Falco Research Console launcher
```

## Development and release checks

```bash
uv sync --locked
make lock-check
make lint
make test
make health
```

`make lock-check` verifies that `uv.lock` matches `pyproject.toml` without modifying it. The product lockfile is regenerated for the Falco 1.0.0 metadata/dependency graph, and the permanent GitHub Actions workflow enforces locked dependency validation, Ruff, unit/API tests, Alembic fresh upgrade plus downgrade/re-upgrade, Compose database bootstrap, and API/Airflow image builds.

The project targets Python `>=3.12,<3.13`. The API runtime container runs as a non-root user.

## Technology references

- [FastAPI](https://fastapi.tiangolo.com/)
- [OpenSearch](https://docs.opensearch.org/)
- [Apache Airflow](https://airflow.apache.org/docs/)
- [Docling](https://docling-project.github.io/docling/)
- [Jina AI embeddings](https://jina.ai/embeddings/)
- [Ollama](https://docs.ollama.com/)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [Langfuse](https://langfuse.com/docs)
- [Redis](https://redis.io/docs/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [uv](https://docs.astral.sh/uv/)

## Licensing and commercial distribution

Falco contains substantial modifications and productization work on top of software originally released by **Jam With AI** under the MIT License. The MIT License permits commercial use, modification, distribution, sublicensing, and sale, while requiring preservation of the upstream copyright and permission notice.

The required upstream notice is retained in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Falco-specific branding, documentation, modifications, support, packaging, and other original additions may be subject to separate commercial terms, but those terms do not remove the rights granted by the upstream MIT License for upstream MIT-licensed material.

Before selling source-code licenses with restrictions on redistribution, define a lawyer-reviewed licensing model that clearly separates upstream MIT material from Falco-specific rights.
