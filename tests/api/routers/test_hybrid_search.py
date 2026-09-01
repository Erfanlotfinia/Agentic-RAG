from src.routers.hybrid_search import hybrid_search
from src.schemas.api.search import HybridSearchRequest


async def test_search_endpoint_basic(client):
    response = await client.post("/api/v1/hybrid-search/", json={"query": "neural networks", "size": 5})

    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "total" in data
    assert "hits" in data
    assert "size" in data
    assert "from" in data

    assert data["query"] == "neural networks"
    assert isinstance(data["total"], int)
    assert isinstance(data["hits"], list)


async def test_search_endpoint_with_latest_papers(client):
    response = await client.post(
        "/api/v1/hybrid-search/", json={"query": "machine learning", "size": 3, "latest_papers": True, "use_hybrid": False}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "machine learning"


async def test_search_endpoint_with_categories(client):
    response = await client.post(
        "/api/v1/hybrid-search/",
        json={"query": "deep learning", "size": 5, "categories": ["cs.AI", "cs.LG"], "latest_papers": False, "use_hybrid": False},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "deep learning"


async def test_search_endpoint_validation_errors(client):
    response = await client.post("/api/v1/hybrid-search/", json={"query": ""})
    assert response.status_code == 422

    response = await client.post("/api/v1/hybrid-search/", json={"query": "test", "size": 0})
    assert response.status_code == 422

    response = await client.post("/api/v1/hybrid-search/", json={"size": 10})
    assert response.status_code == 422


async def test_search_endpoint_pagination(client):
    response = await client.post("/api/v1/hybrid-search/", json={"query": "artificial intelligence", "size": 5, "from": 10})

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "artificial intelligence"


async def test_search_endpoint_all_parameters(client):
    response = await client.post(
        "/api/v1/hybrid-search/",
        json={
            "query": "transformers attention mechanism",
            "size": 8,
            "from": 5,
            "categories": ["cs.AI"],
            "latest_papers": True,
            "use_hybrid": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "transformers attention mechanism"
    assert isinstance(data["total"], int)
    assert isinstance(data["hits"], list)

    for hit in data["hits"]:
        assert "arxiv_id" in hit
        assert "title" in hit
        assert "score" in hit


class _SearchStub:
    def __init__(self, hits=None):
        self.kwargs = None
        self._hits = hits or []

    def health_check(self):
        return True

    def search_unified(self, **kwargs):
        self.kwargs = kwargs
        return {"total": len(self._hits), "hits": self._hits}


class _EmbeddingStub:
    def __init__(self):
        self.calls = 0

    async def embed_query(self, query):
        self.calls += 1
        return [0.1, 0.2]


def _hit(index: int) -> dict:
    return {
        "arxiv_id": f"2501.{index:05d}",
        "title": f"Paper {index}",
        "authors": "Researcher",
        "abstract": "Abstract",
        "published_date": "2026-01-01",
        "pdf_url": f"https://arxiv.org/pdf/2501.{index:05d}.pdf",
        "score": float(index),
        "chunk_text": f"Chunk {index}",
    }


async def test_latest_request_forces_date_sorted_bm25_path():
    search = _SearchStub([_hit(1)])
    embeddings = _EmbeddingStub()
    request = HybridSearchRequest(query="latest retrieval", latest_papers=True, use_hybrid=True, size=5)

    response = await hybrid_search(request, search, embeddings)

    assert embeddings.calls == 0
    assert search.kwargs["latest"] is True
    assert search.kwargs["use_hybrid"] is False
    assert search.kwargs["from_"] == 0
    assert search.kwargs["size"] == 5
    assert response.search_mode == "bm25"


async def test_hybrid_pagination_fetches_ranked_prefix_then_slices_page():
    search = _SearchStub([_hit(i) for i in range(15)])
    embeddings = _EmbeddingStub()
    request = HybridSearchRequest(query="paged retrieval", use_hybrid=True, size=5, **{"from": 10})

    response = await hybrid_search(request, search, embeddings)

    assert embeddings.calls == 1
    assert search.kwargs["use_hybrid"] is True
    assert search.kwargs["from_"] == 0
    assert search.kwargs["size"] == 15
    assert response.search_mode == "hybrid"
    assert [hit.arxiv_id for hit in response.hits] == [f"2501.{i:05d}" for i in range(10, 15)]
