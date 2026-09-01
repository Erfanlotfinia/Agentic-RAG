from unittest.mock import MagicMock

from src.services.opensearch.client import OpenSearchClient


def _client_with_response(response: dict) -> OpenSearchClient:
    client = OpenSearchClient.__new__(OpenSearchClient)
    client.index_name = "arxiv-papers-chunks"
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
    assert result["total"] == 42
    assert result["hits"][0]["chunk_id"] == "chunk-10"


def test_rrf_setup_checks_search_pipeline_endpoint():
    opensearch = OpenSearchClient.__new__(OpenSearchClient)
    opensearch.client = MagicMock()
    opensearch.client.transport.perform_request.return_value = {"hybrid-rrf-pipeline": {}}

    created = opensearch._create_rrf_pipeline(force=False)

    assert created is False
    opensearch.client.transport.perform_request.assert_called_once_with("GET", "/_search/pipeline/hybrid-rrf-pipeline")
