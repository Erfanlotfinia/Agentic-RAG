from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.exceptions import OpenSearchException
from src.services.opensearch.client import OpenSearchClient


def _settings(
    *,
    vector_dimension: int = 1024,
    vector_space_type: str = "cosinesimil",
    rrf_pipeline_name: str = "hybrid-rrf-pipeline",
    hybrid_search_size_multiplier: int = 2,
):
    return SimpleNamespace(
        opensearch=SimpleNamespace(
            vector_dimension=vector_dimension,
            vector_space_type=vector_space_type,
            rrf_pipeline_name=rrf_pipeline_name,
            hybrid_search_size_multiplier=hybrid_search_size_multiplier,
        )
    )


def _client_with_response(response: dict) -> OpenSearchClient:
    client = OpenSearchClient.__new__(OpenSearchClient)
    client.index_name = "arxiv-papers-chunks"
    client.settings = _settings()
    client.client = MagicMock()
    client.client.search.return_value = response
    return client


def test_native_hybrid_search_applies_shared_filter_pagination_and_total():
    response = {
        "hits": {
            "total": {"value": 42},
            "hits": [
                {
                    "_id": "chunk-10",
                    "_score": 0.7,
                    "_source": {"arxiv_id": "2501.00010", "categories": ["cs.AI"], "chunk_text": "context"},
                }
            ],
        }
    }
    opensearch = _client_with_response(response)

    result = opensearch._search_hybrid_native(
        query="agentic retrieval",
        query_embedding=[0.1, 0.2],
        size=5,
        from_=10,
        categories=["cs.AI"],
        min_score=0.2,
    )

    _, kwargs = opensearch.client.search.call_args
    body = kwargs["body"]
    hybrid = body["query"]["hybrid"]

    assert body["from"] == 10
    assert body["size"] == 5
    assert body["min_score"] == 0.2
    assert hybrid["pagination_depth"] == 30
    assert hybrid["filter"] == {"terms": {"categories": ["cs.AI"]}}
    assert hybrid["queries"][1]["knn"]["embedding"]["k"] == 30
    assert kwargs["params"] == {"search_pipeline": "hybrid-rrf-pipeline"}
    assert result["total"] == 42
    assert result["hits"][0]["chunk_id"] == "chunk-10"


def test_unified_search_surfaces_backend_failures():
    opensearch = _client_with_response({})
    opensearch.client.search.side_effect = RuntimeError("backend unavailable")

    with pytest.raises(OpenSearchException, match="Search backend request failed"):
        opensearch.search_unified(query="rag", use_hybrid=False)


def test_rrf_setup_checks_configured_search_pipeline_endpoint():
    opensearch = OpenSearchClient.__new__(OpenSearchClient)
    opensearch.settings = _settings(rrf_pipeline_name="falco-rrf")
    opensearch.client = MagicMock()
    opensearch.client.transport.perform_request.return_value = {"falco-rrf": {}}

    created = opensearch._create_rrf_pipeline(force=False)

    assert created is False
    opensearch.client.transport.perform_request.assert_called_once_with("GET", "/_search/pipeline/falco-rrf")


def test_index_creation_uses_configured_vector_mapping():
    opensearch = OpenSearchClient.__new__(OpenSearchClient)
    opensearch.index_name = "arxiv-papers-chunks"
    opensearch.settings = _settings(vector_dimension=768, vector_space_type="l2")
    opensearch.client = MagicMock()
    opensearch.client.indices.exists.return_value = False

    created = opensearch._create_hybrid_index(force=False)

    assert created is True
    _, kwargs = opensearch.client.indices.create.call_args
    embedding = kwargs["body"]["mappings"]["properties"]["embedding"]
    assert embedding["dimension"] == 768
    assert embedding["method"]["space_type"] == "l2"
