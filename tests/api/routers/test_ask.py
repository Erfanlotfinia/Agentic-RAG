from contextlib import nullcontext

from src.routers.ask import _prepare_chunks_and_sources
from src.schemas.api.ask import AskRequest


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
    assert "text/plain" in response.headers.get("content-type", "")
    assert '"done": true' in response.text


async def test_stream_endpoint_validation_errors(client):
    response = await client.post("/api/v1/stream", json={"query": "", "model": "llama3.2:3b"})
    assert response.status_code == 422


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
