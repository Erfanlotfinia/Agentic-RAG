# API

Falco Agentic RAG exposes its HTTP API through FastAPI. The default local base URL is `http://localhost:8000` and interactive OpenAPI documentation is available at `/docs`.

## Authentication and rate limiting

Built-in API authentication is optional for trusted local development and should be enabled for remotely reachable deployments unless an equivalent stronger authenticated network/ingress policy is in place.

When `AUTH__ENABLED=true`, all `/api/*` endpoints except `/api/v1/health` and `/api/v1/ready` require:

```text
Authorization: Bearer <AUTH__API_KEY>
```

A missing/invalid credential returns HTTP 401 with `WWW-Authenticate: Bearer`.

When `AUTH__RATE_LIMIT_ENABLED=true`, Falco applies a Redis-backed fixed-window limit per authenticated API key. Successful protected responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`. Exceeding the configured limit returns HTTP 429 plus `Retry-After`. If the rate-limit Redis service is unavailable, protected requests return HTTP 503 rather than bypassing the configured limit.

The examples below omit the Bearer header for readability. Add it whenever built-in authentication is enabled.

## Endpoints

| Method | Endpoint | Purpose | Built-in auth |
|---|---|---|---|
| GET | `/api/v1/health` | Diagnostic platform/dependency health; remains HTTP 200 for degraded status reporting | Public |
| GET | `/api/v1/ready` | Readiness probe; returns HTTP 503 when required RAG dependencies are degraded | Public |
| POST | `/api/v1/hybrid-search/` | BM25 or hybrid retrieval | Required when enabled |
| POST | `/api/v1/ask` | Conventional grounded RAG | Required when enabled |
| POST | `/api/v1/stream` | Streaming conventional RAG | Required when enabled |
| POST | `/api/v1/ask-agentic` | Adaptive Agentic RAG | Required when enabled |
| POST | `/api/v1/feedback` | Attach feedback to a Langfuse trace | Required when enabled |

## Agentic RAG

Example:

```bash
curl -X POST http://localhost:8000/api/v1/ask-agentic \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <api-key-if-enabled>' \
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

`session_id` is optional. When provided, recent conversation turns are loaded from Redis and the new turn is persisted for later requests. The same client-provided session ID is returned in the response. Without a supplied session ID, the request is isolated and the response does not expose Falco's internal execution/thread identifier.

The response includes the final answer plus retrieval metadata such as source PDF URLs, chunks used, effective search mode, retrieval attempts, the latest rewritten query when applicable, and a Langfuse trace ID when tracing is enabled.

## Conventional RAG

`POST /api/v1/ask` executes a direct retrieval-and-generation flow. Exact responses may be served from Redis when the query, generation configuration, and requested retrieval mode match a cached response.

The cache key includes:

- query;
- model;
- `top_k`;
- hybrid/BM25 mode;
- categories.

If a hybrid request temporarily falls back to BM25 because query embeddings are unavailable, Falco reports the effective BM25 mode and does not treat that degraded result as a reusable hybrid cache entry.

## Streaming RAG

`POST /api/v1/stream` returns server-sent response lines containing metadata, answer chunks, and a completion event. The included Falco Research Console consumes this endpoint. Streaming responses use the same effective retrieval-mode and cache semantics as conventional RAG.

When built-in authentication is enabled, the Research Console can forward the configured API key via `FALCO_API_KEY`.

## Search

`POST /api/v1/hybrid-search/` supports BM25 and native OpenSearch hybrid retrieval. Hybrid retrieval uses Jina query embeddings and OpenSearch rank fusion. If query embedding fails, retrieval falls back to BM25 and reports `search_mode="bm25"`.

`latest_papers=true` intentionally selects date-sorted BM25 rather than relevance fusion. Pagination uses the request `from`/`size` values, and category filters apply across hybrid retrieval.

## Health and readiness

Diagnostic health:

```bash
curl http://localhost:8000/api/v1/health
```

The health response reports the Falco service version, environment, service name, and dependency status for PostgreSQL, OpenSearch, and Ollama. A degraded dependency is represented in the response body while the endpoint remains available for diagnostics.

Readiness:

```bash
curl -f http://localhost:8000/api/v1/ready
```

The readiness endpoint returns HTTP 503 until the dependencies required for core RAG serving are healthy. Use this endpoint for orchestrator/load-balancer readiness decisions. Both probe endpoints remain accessible without Bearer credentials.

## Feedback

When Langfuse is enabled, Agentic responses can include a trace ID. Use `POST /api/v1/feedback` to attach a score and optional comment to that trace.

If tracing is disabled, feedback submission returns an unavailable response rather than silently discarding feedback.

## Error handling

Validation failures are returned as client errors. Unexpected internal failures are logged server-side and returned to clients as generic server errors rather than exposing raw dependency exception text.

Operational clients should distinguish at least:

- `401`: missing/invalid API credential when built-in authentication is enabled;
- `429`: configured API rate limit exceeded;
- `503`: readiness/dependency failure, including unavailable Redis when rate limiting is enabled;
- ordinary validation errors for malformed requests.

OpenSearch and Ollama are required for full RAG behavior; embeddings, Langfuse, Telegram, and Redis cache/session functionality are configuration-dependent capabilities with the degradation behavior documented in `docs/OPERATIONS.md`.
