import json
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.agents.tools import create_retriever_tool


@pytest.mark.asyncio
async def test_create_retriever_tool_basic(mock_opensearch_client, mock_jina_embeddings_client):
    tool = create_retriever_tool(
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
        top_k=2,
        use_hybrid=True,
    )

    result = json.loads(await tool.ainvoke({"query": "machine learning"}))
    documents = result["documents"]

    assert tool.name == "retrieve_papers"
    assert len(documents) == 2
    assert documents[0]["page_content"].startswith("Transformers")
    assert documents[0]["metadata"]["arxiv_id"] == "1706.03762"
    assert documents[0]["metadata"]["source"] == "https://arxiv.org/pdf/1706.03762.pdf"

    mock_jina_embeddings_client.embed_query.assert_called_once_with("machine learning")
    call_args = mock_opensearch_client.search_unified.call_args
    assert call_args.kwargs["query"] == "machine learning"
    assert call_args.kwargs["size"] == 2
    assert call_args.kwargs["use_hybrid"] is True


@pytest.mark.asyncio
async def test_retriever_tool_empty_results(mock_opensearch_client, mock_jina_embeddings_client):
    mock_opensearch_client.search_unified = Mock(return_value={"hits": []})
    tool = create_retriever_tool(
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
    )

    result = json.loads(await tool.ainvoke({"query": "nonexistent topic"}))
    assert result == {"documents": []}


@pytest.mark.asyncio
async def test_retriever_tool_bm25_mode_does_not_embed(mock_opensearch_client, mock_jina_embeddings_client):
    tool = create_retriever_tool(
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
        top_k=5,
        use_hybrid=False,
        categories=["cs.AI"],
    )

    await tool.ainvoke({"query": "test query"})

    mock_jina_embeddings_client.embed_query.assert_not_called()
    call_args = mock_opensearch_client.search_unified.call_args
    assert call_args.kwargs["size"] == 5
    assert call_args.kwargs["use_hybrid"] is False
    assert call_args.kwargs["categories"] == ["cs.AI"]


@pytest.mark.asyncio
async def test_retriever_tool_embedding_failure_falls_back_to_bm25(mock_opensearch_client, mock_jina_embeddings_client):
    mock_jina_embeddings_client.embed_query = AsyncMock(side_effect=RuntimeError("Jina unavailable"))
    tool = create_retriever_tool(
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
        use_hybrid=True,
    )

    await tool.ainvoke({"query": "test"})

    call_args = mock_opensearch_client.search_unified.call_args
    assert call_args.kwargs["query_embedding"] is None
    assert call_args.kwargs["use_hybrid"] is False


@pytest.mark.asyncio
async def test_retriever_tool_normalizes_metadata(mock_opensearch_client, mock_jina_embeddings_client):
    mock_opensearch_client.search_unified = Mock(
        return_value={
            "hits": [
                {
                    "chunk_text": "Test content",
                    "arxiv_id": "2301.00001v2",
                    "title": "Test Paper",
                    "authors": "Author One, Author Two",
                    "score": 0.95,
                    "section_title": "Introduction",
                }
            ]
        }
    )
    tool = create_retriever_tool(
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
    )

    result = json.loads(await tool.ainvoke({"query": "test"}))
    metadata = result["documents"][0]["metadata"]

    assert metadata["authors"] == ["Author One", "Author Two"]
    assert metadata["source"] == "https://arxiv.org/pdf/2301.00001.pdf"
    assert metadata["section"] == "Introduction"
