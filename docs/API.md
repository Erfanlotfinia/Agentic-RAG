# API

Falco Agentic RAG exposes its HTTP API through FastAPI. The default local base URL is `http://localhost:8000` and interactive OpenAPI documentation is available at `/docs`.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Platform and dependency health |
| POST | `/api/v1/hybrid-search/` | BM25 or hybrid retrieval |
| POST | `/api/v1/ask` | Conventional grounded RAG |
| POST | `/api/v1/stream` | Streaming conventional RAG |
| POST | `/api/v1/ask-agentic` | Adaptive Agentic RAG |
| POST | `/api/v1/feedback` | Attach feedback to a Langfuse trace |

## Agentic RAG

Example:

```bash
curl -X POST http://localhost:8000/api/v1/ask-agentic \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "How does retrieval augmented generation reduce hallucination?",
    "top_k": 5,
    "use_hybrid": true,
    "model": "llama3.2:1b",
    "categories": ["cs.AI", "cs.CL"],
    "session_id": "research-session-42"
  }'
```

The request controls the actual graph configuration. `top_k`, `use_hybrid`, `model`, and `categories` are not response-only metadata.

`session_id` is optional. When provided, recent conversation turns are loaded from Redis and the new turn is persisted for later requests. Without it, the request is isolated.

The response includes the final answer plus retrieval metadata such as source PDF URLs, chunks used, effective search mode, retrieval attempts, and a Langfuse trace ID when tracing is enabled.

## Conventional RAG

`POST /api/v1/ask` executes a direct retrieval-and-generation flow. Exact responses may be served from Redis when the query and retrieval configuration match a cached request.

The cache key includes:

- query;
- model;
- `top_k`;
- hybrid/BM25 mode;
- categories.

## Streaming RAG

`POST /api/v1/stream` returns server-sent response lines containing metadata, answer chunks, and a completion event. The included Falco Research Console consumes this endpoint.

## Search

`POST /api/v1/hybrid-search/` supports BM25 and hybrid retrieval. Hybrid retrieval uses Jina query embeddings and OpenSearch rank fusion. If query embedding fails, retrieval falls back to BM25.

## Health

```bash
curl http://localhost:8000/api/v1/health
```

The health response reports the Falco service version, environment, service name, and dependency status for PostgreSQL, OpenSearch, and Ollama.

## Feedback

When Langfuse is enabled, Agentic responses can include a trace ID. Use `POST /api/v1/feedback` to attach a score and optional comment to that trace.

If tracing is disabled, feedback submission returns an unavailable response rather than silently discarding feedback.

## Error handling

Validation failures are returned as client errors. Agent execution failures are returned as server errors. Integrations should treat OpenSearch/Ollama availability as required for full RAG behavior and embeddings/Langfuse/Telegram as configuration-dependent capabilities.
