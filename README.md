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

<br>

<p align="center">
  <img src="docs/assets/platform-architecture.gif" alt="Falco Agentic RAG Architecture" width="780">
</p>

## Product overview

**Falco Agentic RAG** is a deployable research-intelligence platform for teams that need grounded answers from a continuously indexed technical knowledge base. The included reference deployment is optimized for arXiv computer-science research, while the architecture keeps ingestion, retrieval, generation, state, and observability modular.

Falco combines two paths:

- **Knowledge pipeline:** arXiv → PDF parsing → PostgreSQL → chunking → embeddings → OpenSearch.
- **Serving platform:** FastAPI → search / conventional RAG / streaming RAG / Agentic RAG → OpenSearch + Ollama, with Redis and Langfuse around the request flow.

PostgreSQL is the canonical document store. OpenSearch is the retrieval model. Ollama provides local inference. Jina provides retrieval embeddings. Airflow automates ingestion. Redis provides response caching and Agentic session history. Langfuse provides tracing and feedback.

## Core capabilities

| Capability | What Falco provides |
|---|---|
| Automated ingestion | Scheduled arXiv discovery, PDF download, Docling parsing, persistence, and indexing |
| Hybrid retrieval | BM25 + vector retrieval with Reciprocal Rank Fusion and category filters |
| Agentic RAG | Guardrails, retrieval, document grading, query rewriting, bounded retries, and grounded generation |
| Graceful degradation | Automatic BM25 fallback when query embeddings are unavailable |
| Conversation sessions | Redis-backed bounded Agentic history shared across API workers |
| Local inference | Ollama-backed generation without sending prompts to a hosted LLM provider |
| Observability | Langfuse traces for RAG/graph execution plus feedback capture |
| Multi-channel access | REST API, streaming API, Falco Research Console, and optional Telegram interface |
| Orchestration | Docker Compose stack and scheduled Airflow ingestion |

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
    canonical document store
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
     │                  Redis sessions
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

Request-level `model`, `top_k`, retrieval mode, categories, and optional `session_id` are applied to graph execution. Responses expose the effective search mode, actual source URLs, chunks used, retrieval attempts, trace ID, and a compact reasoning summary.

## Quick start

### Requirements

- Docker with Docker Compose
- Python 3.12 for local development
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Jina API key for hybrid/vector retrieval
- an Ollama model available to the Ollama service
- optional Langfuse credentials
- optional Telegram bot token

### Start Falco

```bash
cp .env.example .env
# Configure required keys and replace all change-me values before deployment.

uv sync
docker compose up --build -d
curl http://localhost:8000/api/v1/health
```

Interactive API documentation is available at `http://localhost:8000/docs`.

### Falco Research Console

```bash
uv run python gradio_launcher.py
```

The local console is available at `http://localhost:7861`.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Platform health and dependency status |
| POST | `/api/v1/hybrid-search/` | BM25 or hybrid chunk retrieval |
| POST | `/api/v1/ask` | Conventional grounded RAG |
| POST | `/api/v1/stream` | Streaming conventional RAG |
| POST | `/api/v1/ask-agentic` | Adaptive Agentic RAG |
| POST | `/api/v1/feedback` | Attach feedback to a Langfuse trace |

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

BM25 remains a first-class retrieval path. When a query embedding is available, Falco executes keyword and vector branches and fuses their rankings using Reciprocal Rank Fusion (`rank_constant=60`). If query embedding fails, retrieval falls back to BM25 instead of failing the request.

```text
text query ─────► BM25 ──┐
                         ├──► RRF ──► top-k chunks
query embedding ─► kNN ──┘
```

## Cache and conversation state

Redis serves two independent responsibilities:

- **Exact response cache** for conventional RAG. Cache identity includes query, model, `top_k`, retrieval mode, and categories.
- **Agentic session history** for explicit `session_id` values. Recent user/assistant turns are bounded and expire using the configured Redis TTL.

Requests without a `session_id` are isolated. Redis-backed history is shared across the four Uvicorn workers used by the default Docker image.

## Observability

Falco targets Langfuse 3.x. Major RAG and graph operations are traced, including guardrails, retrieval, grading, rewriting, and generation. Tracing is optional; the core retrieval/generation path can run with Langfuse disabled.

## Ingestion automation

The `arxiv_paper_ingestion` Airflow DAG runs Monday through Friday at 06:00 UTC by default:

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

See [`airflow/README.md`](airflow/README.md) for pipeline operations.

## Service endpoints

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
- [`docs/API.md`](docs/API.md) — API behavior and request examples
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — environment and service configuration
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — deployment and production checklist
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — health, ingestion, recovery, and backups
- [`SECURITY.md`](SECURITY.md) — deployment security requirements
- [`CHANGELOG.md`](CHANGELOG.md) — product release history
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — upstream licensing notices

## Repository structure

```text
.
├── src/                         # Falco application code
│   ├── main.py                  # FastAPI composition root
│   ├── routers/                 # HTTP API
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic contracts
│   └── services/                # retrieval, agents, LLM, cache, tracing, integrations
├── airflow/                     # scheduled ingestion pipeline
├── docs/                        # product documentation and architecture assets
├── tests/                       # automated test suite
├── compose.yml                  # self-hosted service stack
└── gradio_launcher.py           # Falco Research Console launcher
```

## Development

```bash
uv sync
uv run pytest
make lint
make format
make start
make health
```

The project targets Python `>=3.12,<3.13` and uses Ruff, MyPy, Pytest, and pre-commit tooling.

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
- [uv](https://docs.astral.sh/uv/)

## Licensing and commercial distribution

Falco contains substantial modifications and productization work on top of software originally released by **Jam With AI** under the MIT License. The MIT License permits commercial use, modification, distribution, sublicensing, and sale, while requiring preservation of the upstream copyright and permission notice.

The required upstream notice is retained in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Falco-specific branding, documentation, modifications, support, packaging, and other original additions may be subject to separate commercial terms, but those terms do not remove the rights granted by the upstream MIT License for upstream MIT-licensed material.

Before selling source-code licenses with restrictions on redistribution, define a lawyer-reviewed licensing model that clearly separates upstream MIT material from Falco-specific rights.
