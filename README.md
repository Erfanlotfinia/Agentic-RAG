# Falco — Agentic RAG for Academic Research

Falco is an end-to-end Retrieval-Augmented Generation system for academic research. It ingests arXiv papers, parses and stores the source documents, builds a chunk-level hybrid search index, and serves both conventional RAG and adaptive Agentic RAG APIs.

The project deliberately separates the **offline ingestion/indexing path** from the **online retrieval/generation path**. PostgreSQL is the canonical paper store, OpenSearch is the retrieval/read model, Ollama serves the local LLM, Jina generates retrieval embeddings, Redis provides exact-match response caching, Airflow schedules ingestion, and Langfuse provides observability.

## Architecture

```text
                                  OFFLINE DATA PIPELINE

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
   canonical paper storage
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
             │
──────────────────────────────────────────────────────────────────────────────
                                  ONLINE SERVING
             │
             ▼
           FastAPI
     ┌───────┼───────────┐
     │       │           │
     ▼       ▼           ▼
 Search   Normal RAG   Agentic RAG
     │       │           │
     │     Redis       LangGraph
     │       │           │
     └───────┴─────► OpenSearch
                       │
                       ▼
                     Ollama
                       │
                       ▼
                    Response
```

### Agentic workflow

The Agentic RAG path is a single adaptive LangGraph workflow, not a multi-agent system:

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

The graph validates scope, retrieves chunks, grades the retrieved context, rewrites weak queries, retries retrieval up to a configured limit, and then generates the final answer.

## Main components

| Component | Responsibility |
|---|---|
| FastAPI | HTTP API, application lifecycle, dependency injection |
| PostgreSQL 16 | Canonical arXiv paper metadata and parsed document content |
| Apache Airflow | Scheduled ingestion and indexing orchestration |
| Docling | Scientific PDF parsing |
| OpenSearch 2.19 | BM25, kNN vector search, and hybrid retrieval |
| Jina Embeddings v3 | 1024-dimensional query and passage embeddings |
| Ollama | Local LLM generation and LangChain-compatible model access |
| LangGraph | Agentic workflow orchestration |
| Redis | Exact-match cache for conventional RAG requests |
| Langfuse v3 | Request, retrieval, grading, rewrite, and generation tracing |
| Telegram Bot | Optional mobile interface |
| Gradio | Optional local streaming RAG UI |

## Repository structure

```text
.
├── src/
│   ├── main.py                 # FastAPI composition root and lifecycle
│   ├── dependencies.py         # FastAPI dependency wiring
│   ├── config.py               # Environment-backed settings
│   ├── routers/
│   │   ├── ping.py             # health endpoint
│   │   ├── hybrid_search.py    # BM25/hybrid search API
│   │   ├── ask.py              # conventional + streaming RAG
│   │   └── agentic_ask.py      # Agentic RAG + feedback API
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic request/response schemas
│   └── services/
│       ├── agents/             # LangGraph state, nodes, tools, prompts
│       ├── arxiv/              # arXiv client
│       ├── cache/              # Redis response cache
│       ├── embeddings/         # Jina embeddings client
│       ├── indexing/           # chunking + embedding + OpenSearch indexing
│       ├── langfuse/           # observability
│       ├── ollama/             # LLM client and RAG prompts
│       ├── opensearch/         # search/index client and query builder
│       ├── pdf_parser/         # PDF parsing
│       └── telegram/           # Telegram integration
├── airflow/
│   └── dags/                   # scheduled arXiv ingestion/indexing
├── notebooks/                  # incremental implementation notebooks
├── tests/                      # automated tests
├── compose.yml                 # local service stack
└── gradio_launcher.py          # optional Gradio launcher
```

## Data model and storage responsibilities

### PostgreSQL: source of truth

The `papers` table stores:

- arXiv ID, title, authors, abstract, categories and publication date
- PDF URL
- parsed raw text
- parsed sections and references
- parser metadata and processing state
- created/updated timestamps

PostgreSQL is used by ingestion and re-indexing. Online retrieval does not need to join back to PostgreSQL for every query.

### OpenSearch: retrieval model

Each paper is split into chunks. The OpenSearch document contains chunk content plus denormalized paper metadata:

- `arxiv_id`, `paper_id`, `chunk_index`
- `chunk_text`, word/character offsets and section title
- title, authors, abstract, categories and publication date
- a 1024-dimensional Jina embedding

The vector field uses HNSW with cosine similarity.

## Ingestion and indexing

The Airflow DAG `arxiv_paper_ingestion` runs Monday-Friday at 06:00 UTC:

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

### Fetch stage

`fetch_daily_papers`:

1. selects the target arXiv date;
2. fetches paper metadata;
3. downloads and parses PDFs with Docling;
4. stores metadata and parsed content in PostgreSQL.

### Index stage

`index_papers_hybrid`:

1. reads recently stored papers from PostgreSQL;
2. chunks each paper using the section-aware `TextChunker`;
3. creates Jina `retrieval.passage` embeddings;
4. bulk-indexes chunks and embeddings into OpenSearch.

Existing chunks can be replaced during re-indexing.

## Retrieval

### BM25

Chunk-level BM25 searches use the following default field boosts:

```text
chunk_text^3
title^2
abstract^1
```

Category filtering and highlighting are supported.

### Hybrid search

When a query embedding is available, OpenSearch runs two retrieval branches:

```text
text query ──► BM25 ──┐
                      ├──► Reciprocal Rank Fusion ──► top-k chunks
query embedding ─► kNN┘
```

The project uses OpenSearch's native RRF search pipeline with `rank_constant=60`. If query embedding generation fails in conventional RAG/search, the request degrades to BM25 instead of failing the entire pipeline.

## API

All runtime endpoints are registered from `src/main.py`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/health` | Service health/status |
| POST | `/api/v1/hybrid-search/` | BM25 or hybrid chunk search |
| POST | `/api/v1/ask` | Conventional RAG answer |
| POST | `/api/v1/stream` | Streaming conventional RAG answer |
| POST | `/api/v1/ask-agentic` | Adaptive Agentic RAG answer |
| POST | `/api/v1/feedback` | Submit Langfuse feedback for an Agentic RAG trace |

Interactive API docs are available at `http://localhost:8000/docs`.

## Conventional RAG request flow

`POST /api/v1/ask` follows this path:

```text
request
  │
  ▼
Redis exact-match lookup
  │ miss
  ▼
Jina query embedding
  │
  ▼
OpenSearch BM25/hybrid retrieval
  │
  ▼
RAG prompt construction
  │
  ▼
Ollama generation
  │
  ▼
Redis cache store
  │
  ▼
response + arXiv source URLs
```

The cache key includes query, model, `top_k`, hybrid mode and categories, so only equivalent request parameters share an entry.

## Agentic RAG request flow

`POST /api/v1/ask-agentic` uses the same OpenSearch/Jina/Ollama infrastructure, but LangGraph controls the retrieval loop.

Important runtime configuration includes:

- `top_k`
- hybrid vs BM25 retrieval
- model
- temperature
- guardrail threshold
- maximum retrieval attempts

The response includes the final answer, sources, retrieval attempts, reasoning summary and tracing metadata when tracing is enabled.

## Application lifecycle and dependency injection

`src/main.py` creates long-lived application services during FastAPI startup and stores them in `app.state`:

- settings and database
- OpenSearch
- arXiv client and PDF parser
- Jina embeddings
- Ollama
- Langfuse
- Redis cache
- optional Telegram bot

`src/dependencies.py` exposes those services to routers via FastAPI `Depends`. Agentic RAG is assembled through a factory from the shared OpenSearch, Ollama, embeddings and Langfuse clients.

## Observability

Langfuse traces both conventional and Agentic RAG execution. The Agentic workflow records spans for operations such as:

- guardrail validation
- retrieval initiation/tool execution
- document grading
- query rewriting
- final answer generation

This makes retrieval quality and graph routing inspectable instead of treating the LLM call as a black box.

## Local services

Start the stack with:

```bash
cp .env.example .env
uv sync
docker compose up --build -d
```

Service URLs in the current `compose.yml`:

| Service | URL |
|---|---|
| FastAPI / Swagger | `http://localhost:8000/docs` |
| OpenSearch | `http://localhost:9200` |
| OpenSearch Dashboards | `http://localhost:5601` |
| Airflow | `http://localhost:8080` |
| Ollama | `http://localhost:11434` |
| Langfuse | `http://localhost:3001` |
| Redis | `localhost:6379` |
| PostgreSQL | `localhost:5432` |

Gradio is launched separately:

```bash
uv run python gradio_launcher.py
```

and is available at `http://localhost:7861`.

## Configuration

Copy the example environment file and configure the required integrations:

```bash
cp .env.example .env
```

Common settings include:

- PostgreSQL connection
- OpenSearch host and index settings
- Ollama host/model/timeout
- Jina API key
- Redis host and TTL
- Langfuse keys and host
- optional Telegram bot token and enable flag

See `.env.example` and `src/config.py` for the authoritative configuration surface.

## Development

```bash
# install dependencies
uv sync

# run tests
uv run pytest

# lint / formatting helpers
make lint
make format

# start local infrastructure
make start

# check services
make health
```

The project targets Python `>=3.12,<3.13` and uses Ruff, MyPy, Pytest and pre-commit tooling.

## Design principles

The current architecture is built around a few deliberate choices:

1. **Search fundamentals first.** BM25 remains a first-class retrieval path rather than relying only on vectors.
2. **Hybrid retrieval without manual score weighting.** BM25 and vector rankings are fused with RRF.
3. **Separate canonical and retrieval storage.** PostgreSQL owns paper data; OpenSearch owns query-time retrieval documents.
4. **Reuse retrieval infrastructure.** Conventional RAG, search and Agentic RAG share the same OpenSearch/Jina services.
5. **Bounded agent loops.** Query rewriting/retrieval retries have a maximum attempt limit.
6. **Graceful degradation.** Conventional retrieval can fall back to BM25 when embeddings are unavailable.
7. **Observable execution.** Langfuse captures the major RAG and graph decisions.

## Incremental notebooks

The `notebooks/` directory documents the evolution of the system from infrastructure through Agentic RAG. These notebooks are useful for learning and historical implementation context, while **the runtime source under `src/`, the Airflow DAGs, and `compose.yml` are the authoritative description of the current application**.

## License

See the repository license for usage terms.
