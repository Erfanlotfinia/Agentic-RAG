from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.main import app
from src.services.langfuse.client import LangfuseTracer


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Async backend for testing."""
    return "asyncio"


@pytest.fixture
async def client():
    """HTTP client whose application lifespan is fully isolated from external services."""
    mock_database = MagicMock()
    mock_session = MagicMock()

    @contextmanager
    def _session_scope():
        yield mock_session

    mock_database.get_session.side_effect = _session_scope

    mock_opensearch = MagicMock()
    mock_opensearch.health_check.return_value = True
    mock_opensearch.setup_indices.return_value = {"hybrid_index": False, "rrf_pipeline": False}
    mock_opensearch.client.count.return_value = {"count": 0}
    mock_opensearch.get_index_stats.return_value = {
        "index_name": "arxiv-papers-chunks",
        "exists": True,
        "document_count": 0,
    }
    mock_opensearch.search_unified.return_value = {"total": 0, "hits": []}

    mock_embeddings = MagicMock()
    mock_embeddings.embed_query = AsyncMock(return_value=[0.1, 0.2])
    mock_embeddings.close = AsyncMock()

    mock_ollama = MagicMock()
    mock_ollama.generate_rag_answer = AsyncMock(return_value={"answer": "Test answer"})

    mock_agentic = MagicMock()
    mock_agentic.ask = AsyncMock(
        return_value={
            "query": "test",
            "answer": "Test answer",
            "sources": [],
            "chunks_used": 0,
            "search_mode": "bm25",
            "reasoning_steps": [],
            "retrieval_attempts": 0,
            "rewritten_query": None,
            "session_id": None,
            "trace_id": None,
        }
    )

    settings = Settings()
    disabled_langfuse = LangfuseTracer(settings)

    health_ollama = MagicMock()
    health_ollama.health_check = AsyncMock(return_value={"status": "healthy", "message": "Available"})

    with (
        patch("src.main.make_database", return_value=mock_database),
        patch("src.main.make_opensearch_client", return_value=mock_opensearch),
        patch("src.main.make_arxiv_client", return_value=MagicMock()),
        patch("src.main.make_pdf_parser_service", return_value=MagicMock()),
        patch("src.main.make_embeddings_service", return_value=mock_embeddings),
        patch("src.main.make_ollama_client", return_value=mock_ollama),
        patch("src.main.make_langfuse_tracer", return_value=disabled_langfuse),
        patch("src.main.make_cache_client", return_value=None),
        patch("src.main.make_agentic_rag_service", return_value=mock_agentic),
        patch("src.main.make_telegram_service", return_value=None),
        patch("src.routers.ping.OllamaClient", return_value=health_ollama),
    ):
        async with LifespanManager(app) as manager:
            async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as http_client:
                yield http_client
