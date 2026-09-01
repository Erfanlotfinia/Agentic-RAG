# Architecture

Falco Agentic RAG is split into a knowledge pipeline and a serving platform. The separation keeps document processing asynchronous and makes query-time retrieval independent from the canonical document database.

## Knowledge pipeline

```text
arXiv API / PDFs
       │
       ▼
ArxivClient + MetadataFetcher
       │
       ▼
Docling PDF parsing
       │
       ▼
PostgreSQL
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

The scheduled Airflow pipeline discovers papers, parses source PDFs, writes canonical content to PostgreSQL, creates retrieval chunks, generates passage embeddings, and updates OpenSearch.

## Serving platform

FastAPI exposes search, conventional RAG, streaming RAG, Agentic RAG, feedback, and health endpoints. Long-lived clients are initialized once during application startup and shared through `app.state`.

### Storage responsibilities

**PostgreSQL** is the canonical document store. It contains arXiv metadata, PDF URLs, parsed text, sections, references, parser metadata, and processing state.

**OpenSearch** is the query-time retrieval model. Documents are denormalized chunks containing text, paper metadata, category information, section information, and 1024-dimensional embeddings.

**Redis** has two responsibilities: exact conventional-RAG response caching and bounded Agentic session history.

## Retrieval

BM25 is a first-class retrieval mode. When a query embedding is available, Falco executes BM25 and kNN branches and combines their rankings with Reciprocal Rank Fusion. The configured RRF rank constant is 60.

```text
text query ─────► BM25 ──┐
                         ├──► RRF ──► top-k chunks
query embedding ─► kNN ──┘
```

If the query-embedding call fails, the request degrades to BM25 rather than failing the complete retrieval flow.

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

Request-level `model`, `top_k`, retrieval mode, and categories are applied to graph execution. The response reports the effective retrieval mode and actual retrieval metadata.

## Sessions

An explicit `session_id` enables bounded conversational history. Recent user/assistant turns are persisted in Redis and restored into subsequent graph invocations. This design is worker-safe across the four Uvicorn workers used by the default image.

Requests without `session_id` are isolated.

## Generation

Ollama provides the local generation layer. Conventional and Agentic RAG both ground generation on OpenSearch retrieval results. Agentic answer generation is additionally gated by relevance grading and bounded query rewriting.

## Observability

Langfuse 3.x captures root RAG/Agentic requests and major graph operations. Trace metadata includes retrieval and generation context where available. Feedback can be attached to a trace through the feedback endpoint.

## Optional interfaces

The HTTP API is the primary integration surface. Falco also includes:

- a Gradio-based Research Console for local interactive use;
- an optional Telegram bot backed by the same application-scoped Agentic RAG service.
