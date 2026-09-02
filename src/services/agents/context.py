from dataclasses import dataclass
from typing import List, Optional

from langfuse._client.span import LangfuseSpan
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient


@dataclass
class Context:
    """Runtime context for agent dependencies and request-scoped options."""

    ollama_client: OllamaClient
    opensearch_client: OpenSearchClient
    embeddings_client: JinaEmbeddingsClient
    langfuse_tracer: Optional[LangfuseTracer]
    trace: Optional[LangfuseSpan] = None
    langfuse_enabled: bool = False
    model_name: str = "llama3.2:1b"
    temperature: float = 0.0
    top_k: int = 3
    use_hybrid: bool = True
    categories: Optional[List[str]] = None
    max_retrieval_attempts: int = 2
    guardrail_threshold: int = 60
