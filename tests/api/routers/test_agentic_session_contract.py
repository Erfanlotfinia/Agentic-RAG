from unittest.mock import AsyncMock

from fastapi import HTTPException

from src.routers.agentic_ask import ask_agentic
from src.schemas.api.ask import AskRequest


def _result(session_id: str) -> dict:
    return {
        "query": "question",
        "answer": "answer",
        "sources": [],
        "chunks_used": 0,
        "search_mode": "bm25",
        "reasoning_steps": [],
        "retrieval_attempts": 0,
        "rewritten_query": None,
        "trace_id": None,
        "session_id": session_id,
    }


async def test_stateless_agentic_request_does_not_expose_internal_thread_id():
    service = AsyncMock()
    service.ask.return_value = _result("request-internal-id")

    response = await ask_agentic(AskRequest(query="question", use_hybrid=False), service)

    assert response.session_id is None


async def test_agentic_response_echoes_persisted_client_session_id():
    service = AsyncMock()
    service.ask.return_value = _result("research-session-1")

    response = await ask_agentic(
        AskRequest(query="question", use_hybrid=False, session_id="research-session-1"),
        service,
    )

    assert response.session_id == "research-session-1"


async def test_agentic_internal_error_does_not_leak_exception_text():
    service = AsyncMock()
    service.ask.side_effect = RuntimeError("postgresql://secret-host/internal")

    try:
        await ask_agentic(AskRequest(query="question"), service)
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "secret-host" not in exc.detail
    else:
        raise AssertionError("Expected HTTPException")
