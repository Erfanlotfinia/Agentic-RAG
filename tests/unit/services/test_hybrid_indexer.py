from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.services.indexing.hybrid_indexer import HybridIndexingService


def _chunk(arxiv_id: str = "2501.12345v1", index: int = 0):
    return SimpleNamespace(
        text="retrievable chunk",
        arxiv_id=arxiv_id,
        paper_id="paper-1",
        metadata=SimpleNamespace(
            chunk_index=index,
            word_count=2,
            start_char=0,
            end_char=17,
            section_title="Introduction",
        ),
    )


@pytest.mark.asyncio
async def test_replace_indexes_new_set_before_deleting_stale_chunks():
    chunker = MagicMock()
    chunker.chunk_paper.return_value = [_chunk(index=0), _chunk(index=1)]

    embeddings = MagicMock()
    embeddings.embed_passages = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    embeddings.close = AsyncMock()

    opensearch = MagicMock()
    opensearch.bulk_index_chunks.return_value = {"success": 2, "failed": 0}

    service = HybridIndexingService(chunker, embeddings, opensearch)
    stats = await service.index_paper(
        {
            "id": "paper-1",
            "arxiv_id": "2501.12345v1",
            "title": "Paper",
            "authors": ["Author"],
            "abstract": "Abstract",
            "categories": ["cs.AI"],
            "published_date": "2026-01-01T00:00:00Z",
        },
        replace_existing=True,
    )

    assert stats["errors"] == 0
    payload = opensearch.bulk_index_chunks.call_args.args[0]
    assert [item["document_id"] for item in payload] == ["2501.12345v1:0", "2501.12345v1:1"]
    opensearch.delete_stale_paper_chunks.assert_called_once_with(
        "2501.12345v1",
        ["2501.12345v1:0", "2501.12345v1:1"],
    )


@pytest.mark.asyncio
async def test_replace_preserves_existing_chunks_when_embedding_fails():
    chunker = MagicMock()
    chunker.chunk_paper.return_value = [_chunk()]

    embeddings = MagicMock()
    embeddings.embed_passages = AsyncMock(side_effect=RuntimeError("embedding unavailable"))
    embeddings.close = AsyncMock()

    opensearch = MagicMock()
    service = HybridIndexingService(chunker, embeddings, opensearch)

    stats = await service.index_paper(
        {"id": "paper-1", "arxiv_id": "2501.12345v1", "title": "Paper", "abstract": "Abstract"},
        replace_existing=True,
    )

    assert stats["errors"] == 1
    opensearch.bulk_index_chunks.assert_not_called()
    opensearch.delete_stale_paper_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_partial_bulk_write_does_not_delete_previous_set():
    chunker = MagicMock()
    chunker.chunk_paper.return_value = [_chunk(index=0), _chunk(index=1)]

    embeddings = MagicMock()
    embeddings.embed_passages = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    embeddings.close = AsyncMock()

    opensearch = MagicMock()
    opensearch.bulk_index_chunks.return_value = {"success": 1, "failed": 1}

    service = HybridIndexingService(chunker, embeddings, opensearch)
    stats = await service.index_paper(
        {"id": "paper-1", "arxiv_id": "2501.12345v1", "title": "Paper", "abstract": "Abstract"},
        replace_existing=True,
    )

    assert stats["errors"] == 1
    opensearch.delete_stale_paper_chunks.assert_not_called()
