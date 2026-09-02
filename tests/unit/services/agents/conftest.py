import json
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.services.agents.context import Context


@pytest.fixture
def mock_opensearch_client():
    client = Mock()
    client.search_unified = Mock(
        return_value={
            "hits": [
                {
                    "chunk_text": "Transformers use self-attention to model token relationships.",
                    "arxiv_id": "1706.03762",
                    "title": "Attention Is All You Need",
                    "authors": ["A. Author"],
                    "score": 0.95,
                    "section_name": "Introduction",
                },
                {
                    "chunk_text": "Transformers can be pretrained and adapted to downstream tasks.",
                    "arxiv_id": "1810.04805",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                    "authors": ["B. Author"],
                    "score": 0.9,
                    "section_name": "Background",
                },
            ]
        }
    )
    return client


@pytest.fixture
def mock_jina_embeddings_client():
    client = Mock()
    client.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return client


@pytest.fixture
def mock_ollama_client():
    client = Mock()
    llm = Mock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mock model response"))
    client.create_llm = Mock(return_value=llm)
    return client


@pytest.fixture
def test_context(mock_opensearch_client, mock_ollama_client, mock_jina_embeddings_client):
    return Context(
        ollama_client=mock_ollama_client,
        opensearch_client=mock_opensearch_client,
        embeddings_client=mock_jina_embeddings_client,
        langfuse_tracer=None,
        trace=None,
        langfuse_enabled=False,
        model_name="llama3.2:1b",
        temperature=0.0,
        top_k=3,
        use_hybrid=True,
        categories=None,
        max_retrieval_attempts=2,
        guardrail_threshold=60,
    )


@pytest.fixture
def sample_human_message():
    return HumanMessage(content="What is machine learning?")


@pytest.fixture
def sample_ai_message():
    return AIMessage(content="Machine learning uses data to learn predictive patterns.")


@pytest.fixture
def sample_tool_message():
    payload = {
        "documents": [
            {
                "page_content": "Transformers use self-attention to model token relationships.",
                "metadata": {
                    "arxiv_id": "1706.03762",
                    "title": "Attention Is All You Need",
                    "authors": ["A. Author"],
                    "score": 0.95,
                    "source": "https://arxiv.org/pdf/1706.03762.pdf",
                    "section": "Introduction",
                    "search_mode": "hybrid",
                },
            }
        ],
        "search_mode": "hybrid",
    }
    return ToolMessage(
        content=json.dumps(payload),
        tool_call_id="retrieve_test_1",
        name="retrieve_papers",
    )
