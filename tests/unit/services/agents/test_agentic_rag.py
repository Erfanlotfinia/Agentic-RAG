"""Tests for AgenticRAGService runtime behavior."""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.config import GraphConfig
from src.services.agents.models import GuardrailScoring, SourceItem


@pytest.fixture
def test_service(mock_opensearch_client, mock_ollama_client, mock_jina_embeddings_client):
    config = GraphConfig(
        model="llama3.2:1b",
        temperature=0.0,
        top_k=3,
        use_hybrid=True,
        max_retrieval_attempts=2,
        guardrail_threshold=60,
    )
    return AgenticRAGService(
        opensearch_client=mock_opensearch_client,
        ollama_client=mock_ollama_client,
        embeddings_client=mock_jina_embeddings_client,
        langfuse_tracer=None,
        cache_client=None,
        graph_config=config,
    )


def _final_state(query="Test query"):
    return {
        "messages": [HumanMessage(content=query), AIMessage(content="Test answer")],
        "retrieval_attempts": 0,
        "guardrail_result": GuardrailScoring(score=85, reason="Relevant"),
        "sources": [],
        "relevant_sources": [],
        "grading_results": [],
        "metadata": {},
        "original_query": query,
        "rewritten_query": None,
        "routing_decision": "generate_answer",
        "relevant_tool_artefacts": None,
    }


class TestAgenticRAGServiceInitialization:
    def test_service_initialization(self, test_service):
        assert test_service.opensearch is not None
        assert test_service.ollama is not None
        assert test_service.embeddings is not None
        assert test_service.graph is not None

    def test_graph_config_values(self, test_service):
        assert test_service.graph_config.model == "llama3.2:1b"
        assert test_service.graph_config.top_k == 3
        assert test_service.graph_config.use_hybrid is True
        assert test_service.graph_config.max_retrieval_attempts == 2
        assert test_service.graph_config.guardrail_threshold == 60


class TestAgenticRAGAskMethod:
    @pytest.mark.asyncio
    async def test_ask_empty_query_validation(self, test_service):
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await test_service.ask(query="")
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await test_service.ask(query="   ")

    @pytest.mark.asyncio
    async def test_ask_with_model_override(self, test_service):
        test_service.graph.ainvoke = AsyncMock(return_value=_final_state())

        result = await test_service.ask(query="Test query", model="llama3.2:3b", session_id="session-1")

        assert result["answer"] == "Test answer"
        call = test_service.graph.ainvoke.call_args
        assert call.kwargs["context"].model_name == "llama3.2:3b"
        assert call.kwargs["config"]["configurable"]["thread_id"] == "session-1"

    @pytest.mark.asyncio
    async def test_request_retrieval_options_build_matching_graph(self, test_service):
        tool_payload = json.dumps(
            {
                "documents": [
                    {
                        "page_content": "Relevant chunk",
                        "metadata": {
                            "arxiv_id": "1706.03762",
                            "title": "Attention Is All You Need",
                            "authors": ["A. Author"],
                            "score": 0.9,
                            "source": "https://arxiv.org/pdf/1706.03762.pdf",
                        },
                    }
                ]
            }
        )
        state = _final_state("custom query")
        state["messages"] = [
            HumanMessage(content="custom query"),
            ToolMessage(content=tool_payload, tool_call_id="retrieve_1", name="retrieve_papers"),
            AIMessage(content="custom answer"),
        ]
        state["retrieval_attempts"] = 1
        state["relevant_sources"] = [
            SourceItem(
                arxiv_id="1706.03762",
                title="Attention Is All You Need",
                authors=["A. Author"],
                url="https://arxiv.org/pdf/1706.03762.pdf",
                relevance_score=0.9,
            )
        ]

        dynamic_graph = Mock()
        dynamic_graph.ainvoke = AsyncMock(return_value=state)
        test_service._build_graph = Mock(return_value=dynamic_graph)

        result = await test_service.ask(
            query="custom query",
            top_k=5,
            use_hybrid=False,
            categories=["cs.AI"],
            session_id="research-thread",
        )

        test_service._build_graph.assert_called_once_with(top_k=5, use_hybrid=False, categories=["cs.AI"])
        call = dynamic_graph.ainvoke.call_args
        assert call.kwargs["context"].top_k == 5
        assert call.kwargs["context"].use_hybrid is False
        assert call.kwargs["context"].categories == ["cs.AI"]
        assert call.kwargs["config"]["configurable"]["thread_id"] == "research-thread"
        assert result["sources"] == ["https://arxiv.org/pdf/1706.03762.pdf"]
        assert result["chunks_used"] == 1
        assert result["search_mode"] == "bm25"

    @pytest.mark.asyncio
    async def test_session_history_is_loaded_and_stored(self, test_service):
        cache = Mock()
        cache.get_conversation_history = AsyncMock(
            return_value=[
                {"role": "user", "content": "What is attention?"},
                {"role": "assistant", "content": "Attention weights relevant tokens."},
            ]
        )
        cache.store_conversation_turn = AsyncMock(return_value=True)
        test_service.cache_client = cache
        test_service.graph.ainvoke = AsyncMock(return_value=_final_state("And transformers?"))

        await test_service.ask(query="And transformers?", session_id="shared-session")

        state_input = test_service.graph.ainvoke.call_args.args[0]
        assert [message.content for message in state_input["messages"]] == [
            "What is attention?",
            "Attention weights relevant tokens.",
            "And transformers?",
        ]
        cache.store_conversation_turn.assert_awaited_once_with(
            session_id="shared-session",
            user_message="And transformers?",
            assistant_message="Test answer",
        )


class TestAgenticRAGGraphVisualization:
    def test_get_graph_mermaid(self, test_service):
        mermaid = test_service.get_graph_mermaid()
        assert isinstance(mermaid, str)
        assert len(mermaid) > 0
        assert "graph" in mermaid.lower() or "flowchart" in mermaid.lower()


class TestAgenticRAGErrorHandling:
    @pytest.mark.asyncio
    async def test_ask_with_graph_execution_error(self, test_service):
        test_service.graph.ainvoke = AsyncMock(side_effect=Exception("Graph execution failed"))
        with pytest.raises(Exception, match="Graph execution failed"):
            await test_service.ask(query="Test query", session_id="error-test")
