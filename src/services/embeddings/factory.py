from typing import Optional

from src.config import Settings, get_settings

from .jina_client import JinaEmbeddingsClient


def make_embeddings_service(settings: Optional[Settings] = None) -> JinaEmbeddingsClient:
    """Create the shared Jina embeddings service from application settings."""
    if settings is None:
        settings = get_settings()

    return JinaEmbeddingsClient(
        api_key=settings.jina_api_key,
        dimensions=settings.opensearch.vector_dimension,
    )


def make_embeddings_client(settings: Optional[Settings] = None) -> JinaEmbeddingsClient:
    """Create a Jina embeddings client from application settings."""
    if settings is None:
        settings = get_settings()

    return JinaEmbeddingsClient(
        api_key=settings.jina_api_key,
        dimensions=settings.opensearch.vector_dimension,
    )
