from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from src.services.langfuse.client import LangfuseTracer


def _tracer_with_client():
    tracer = object.__new__(LangfuseTracer)
    tracer.client = Mock()
    return tracer


def test_create_span_uses_parent_span_when_available():
    tracer = _tracer_with_client()
    parent = Mock()
    child = Mock()
    parent.start_span.return_value = child

    result = tracer.create_span(
        trace=parent,
        name="document_grading",
        input_data={"query": "transformers"},
        metadata={"node": "grade_documents"},
    )

    assert result is child
    parent.start_span.assert_called_once_with(
        name="document_grading",
        input={"query": "transformers"},
        metadata={"node": "grade_documents"},
    )
    tracer.client.start_span.assert_not_called()


def test_create_span_falls_back_to_client():
    tracer = _tracer_with_client()
    child = Mock()
    tracer.client.start_span.return_value = child

    result = tracer.create_span(
        trace=None,
        name="retrieval",
        input_data={"query": "rag"},
    )

    assert result is child
    tracer.client.start_span.assert_called_once_with(
        name="retrieval",
        input={"query": "rag"},
        metadata={},
    )


def test_update_span_does_not_end_span():
    tracer = _tracer_with_client()
    span = Mock()

    tracer.update_span(span, output={"ok": True})

    span.update.assert_called_once_with(output={"ok": True})
    span.end.assert_not_called()


def test_end_span_updates_and_ends():
    tracer = _tracer_with_client()
    span = Mock()

    tracer.end_span(
        span,
        output={"relevant": True},
        metadata={"latency_ms": 12.5},
    )

    span.update.assert_called_once_with(
        output={"relevant": True},
        metadata={"latency_ms": 12.5},
    )
    span.end.assert_called_once()


def test_trace_rag_request_sets_v3_trace_attributes():
    tracer = _tracer_with_client()
    span = Mock()

    @contextmanager
    def root_context():
        yield span

    tracer.client.start_as_current_span.return_value = root_context()

    with tracer.trace_rag_request(
        query="What is RAG?",
        user_id="user-1",
        session_id="session-1",
        metadata={"pipeline": "rag"},
    ) as active_span:
        assert active_span is span

    span.update.assert_called_once_with(
        input={"query": "What is RAG?"},
        metadata={"pipeline": "rag"},
    )
    tracer.client.update_current_trace.assert_called_once_with(
        user_id="user-1",
        session_id="session-1",
        metadata={"pipeline": "rag"},
        input={"query": "What is RAG?"},
        name="rag_request",
    )


def test_trace_rag_request_does_not_swallow_body_exception():
    tracer = _tracer_with_client()
    span = Mock()

    @contextmanager
    def root_context():
        yield span

    tracer.client.start_as_current_span.return_value = root_context()

    with pytest.raises(RuntimeError, match="boom"):
        with tracer.trace_rag_request(query="test"):
            raise RuntimeError("boom")
