import os

import pytest
from src.config import Settings


def test_settings_initialization():
    """Test settings can be initialized with product defaults."""
    settings = Settings()

    assert settings.app_version == "1.0.0"
    assert settings.debug is False
    assert settings.environment == "development"
    assert settings.service_name == "falco-agentic-rag-api"


def test_settings_postgres_defaults():
    """Test PostgreSQL default configuration."""
    settings = Settings()

    assert "postgresql://" in settings.postgres_database_url
    assert settings.postgres_echo_sql is False
    assert settings.postgres_pool_size == 20
    assert settings.postgres_max_overflow == 0


def test_settings_opensearch_defaults():
    """Test OpenSearch default configuration."""
    settings = Settings()

    assert settings.opensearch.host == "http://localhost:9200"
    assert settings.opensearch.index_name == "arxiv-papers"


def test_settings_ollama_defaults():
    """Test Ollama default configuration."""
    settings = Settings()

    expected_host = "http://ollama:11434" if "OLLAMA_HOST" not in os.environ else settings.ollama_host
    assert settings.ollama_host in ["http://localhost:11434", "http://ollama:11434"]
