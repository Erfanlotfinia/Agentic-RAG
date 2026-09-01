from typing import Optional

from src.services.cache.client import CacheClient
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient

from .agentic_rag import AgenticRAGService
from .config import GraphConfig


def make_agentic_rag_service(
    opensearch_client: OpenSearchClient,
    ollama_client: OllamaClient,
    embeddings_client: JinaEmbeddingsClient,
    langfuse_tracer: Optional[LangfuseTracer] = None,
    cache_client: Optional[CacheClient] = None,
    model: Optional[str] = None,
    top_k: int = 3,
    use_hybrid: bool = True,
    max_retrieval_attempts: int = 2,
    guardrail_threshold: int = 60,
) -> AgenticRAGService:
    """Create a configured AgenticRAGService from shared application clients."""
    config_kwargs = {
        "top_k": top_k,
        "use_hybrid": use_hybrid,
        "max_retrieval_attempts": max_retrieval_attempts,
        "guardrail_threshold": guardrail_threshold,
    }
    if model:
        config_kwargs["model"] = model

    return AgenticRAGService(
        opensearch_client=opensearch_client,
        ollama_client=ollama_client,
        embeddings_client=embeddings_client,
        langfuse_tracer=langfuse_tracer,
        cache_client=cache_client,
        graph_config=GraphConfig(**config_kwargs),
    )
