from contextlib import nullcontext

from src.routers.ask import _cache_matches_requested_mode, _prepare_chunks_and_sources
from src.schemas.api.ask import AskRequest, AskResponse


async def test_ask_endpoint_basic(client):
    response = await client.post("/api/v1/ask", json={"query": "What is machine learning?", "model": "llama3.2:3b"})

    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "answer" in data
    assert "sources" in data
    assert "chunks_used" in data
    assert "search_mode" in data

    assert data["query"] == "What is machine learning?"
    assert isinstance(data["sources"], list)
    assert isinstance(data["chunks_used"], int)


async def test_ask_endpoint_with_hybrid_search(client):
    response = await client.post(
        "/api/v1/ask", json={"query": "neural networks", "model": "llama3.2:3b", "use_hybrid": True, "top_k": 5}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "neural networks"
    assert data["search_mode"] == "hybrid"


async def test_ask_endpoint_with_categories(client):
    response = await client.post(
        "/api/v1/ask", json={"query": "computer vision", "model": "llama3.2:3b", "categories": ["cs.CV", "cs.AI"], "top_k": 3}
    )

    assert response.status_code == 200


async def test_ask_endpoint_validation_errors(client):
    response = await client.post("/api/v1/ask", json={"query": "", "model": "llama3.2:3b"})
    assert response.status_code == 422

    response = await client.post("/api/v1/ask", json={"model": "llama3.2:3b"})
    assert response.status_code == 422

    response = await client.post("/api/v1/ask", json={"query": "test", "model": "llama3.2:3b", "top_k": 0})
    assert response.status_code == 422


async def test_stream_endpoint_basic(client):
    response = await client.post("/api/v1/stream", json={"query": "What is deep learning?", "model": "llama3.2:3b"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert response.headers.get("x-accel-buffering") == "no"
    assert '"done": true' in response.text


async def test_stream_endpoint_validation_errors(client):
    response = await client.post("/api/v1/stream", json={"query": "", "model": "llama3.2:3b"})
    assert response.status_code == 422


def test_hybrid_request_rejects_cached_bm25_fallback():
    request = AskRequest(query="agentic retrieval", use_hybrid=True)
    cached = AskResponse(
        query=request.query,
        answer="fallback answer",
        sources=[],
        chunks_used=1,
        search_mode="bm25",
    )

    assert _cache_matches_requested_mode(request, cached) is False


def test_cache_accepts_response_when_retrieval_mode_matches():
    hybrid_request = AskRequest(query="hybrid", use_hybrid=True)
    hybrid_response = AskResponse(query="hybrid", answer="answer", sources=[], chunks_used=1, search_mode="hybrid")
    bm25_request = AskRequest(query="bm25", use_hybrid=False)
    bm25_response = AskResponse(query="bm25", answer="answer", sources=[], chunks_used=1, search_mode="bm25")

    assert _cache_matches_requested_mode(hybrid_request, hybrid_response) is True
    assert _cache_matches_requested_mode(bm25_request, bm25_response) is True


class _StubTracer:
    tracer = None

    def trace_embedding(self, trace, query):
        return nullcontext(None)

    def trace_search(self, trace, query, top_k):
        return nullcontext(None)

    def end_search(self, span, chunks, arxiv_ids, total):
        return None


class _StubSearch:
    def __init__(self):
        self.use_hybrid = None

    def search_unified(self, **kwargs):
        self.use_hybrid = kwargs["use_hybrid"]
        return {"total": 1, "hits": [{"arxiv_id": "2501.12345v2", "chunk_text": "retrieved context"}]}


class _WorkingEmbeddings:
    async def embed_query(self, query):
        return [0.1, 0.2]


class _FailingEmbeddings:
    async def embed_query(self, query):
        raise RuntimeError("embedding service unavailable")


async def test_prepare_chunks_reports_hybrid_when_embedding_succeeds():
    request = AskRequest(query="hybrid retrieval", use_hybrid=True)
    search = _StubSearch()

    chunks, sources, _, search_mode = await _prepare_chunks_and_sources(
        request, search, _WorkingEmbeddings(), _StubTracer()
    )

    assert chunks
    assert sources == ["https://arxiv.org/pdf/2501.12345.pdf"]
    assert search.use_hybrid is True
    assert search_mode == "hybrid"


async def test_prepare_chunks_reports_bm25_when_embedding_falls_back():
    request = AskRequest(query="fallback retrieval", use_hybrid=True)
    search = _StubSearch()

    chunks, sources, _, search_mode = await _prepare_chunks_and_sources(
        request, search, _FailingEmbeddings(), _StubTracer()
    )

    assert chunks
    assert sources == ["https://arxiv.org/pdf/2501.12345.pdf"]
    assert search.use_hybrid is False
    assert search_mode == "bm25"
