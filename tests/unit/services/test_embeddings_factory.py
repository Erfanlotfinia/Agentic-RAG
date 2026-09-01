from types import SimpleNamespace
from unittest.mock import patch

from src.services.embeddings.factory import make_embeddings_client, make_embeddings_service


def _settings(dimension: int = 768):
    return SimpleNamespace(
        jina_api_key="test-jina-key",
        opensearch=SimpleNamespace(vector_dimension=dimension),
    )


def test_embeddings_service_uses_opensearch_vector_dimension():
    settings = _settings(768)

    with patch("src.services.embeddings.factory.JinaEmbeddingsClient") as client_cls:
        make_embeddings_service(settings)

    client_cls.assert_called_once_with(api_key="test-jina-key", dimensions=768)


def test_embeddings_client_uses_opensearch_vector_dimension():
    settings = _settings(512)

    with patch("src.services.embeddings.factory.JinaEmbeddingsClient") as client_cls:
        make_embeddings_client(settings)

    client_cls.assert_called_once_with(api_key="test-jina-key", dimensions=512)
