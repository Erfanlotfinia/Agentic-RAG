import json
from unittest.mock import Mock

import pytest

from src.config import RedisSettings
from src.services.cache.client import CacheClient


@pytest.fixture
def cache_client():
    redis_client = Mock()
    settings = RedisSettings(ttl_hours=6)
    return CacheClient(redis_client=redis_client, settings=settings), redis_client


@pytest.mark.asyncio
async def test_get_conversation_history(cache_client):
    client, redis_client = cache_client
    redis_client.get.return_value = json.dumps(
        [
            {"role": "user", "content": "What is attention?"},
            {"role": "assistant", "content": "Attention weights relevant tokens."},
        ]
    )

    history = await client.get_conversation_history("session-1")

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    redis_client.get.assert_called_once()
    assert redis_client.get.call_args.args[0].startswith("agentic_session:")


@pytest.mark.asyncio
async def test_store_conversation_turn_appends_and_bounds_history(cache_client):
    client, redis_client = cache_client
    existing = []
    for index in range(10):
        existing.extend(
            [
                {"role": "user", "content": f"q{index}"},
                {"role": "assistant", "content": f"a{index}"},
            ]
        )

    redis_client.get.return_value = json.dumps(existing)
    redis_client.set.return_value = True

    stored = await client.store_conversation_turn(
        session_id="session-1",
        user_message="latest question",
        assistant_message="latest answer",
        max_turns=10,
    )

    assert stored is True
    key, payload = redis_client.set.call_args.args[:2]
    saved_history = json.loads(payload)

    assert key.startswith("agentic_session:")
    assert len(saved_history) == 20
    assert saved_history[-2:] == [
        {"role": "user", "content": "latest question"},
        {"role": "assistant", "content": "latest answer"},
    ]
    assert redis_client.set.call_args.kwargs["ex"] == client.ttl


@pytest.mark.asyncio
async def test_invalid_session_payload_fails_open(cache_client):
    client, redis_client = cache_client
    redis_client.get.return_value = "not-json"

    history = await client.get_conversation_history("session-1")

    assert history == []


@pytest.mark.asyncio
async def test_clear_conversation_history(cache_client):
    client, redis_client = cache_client
    redis_client.delete.return_value = 1

    cleared = await client.clear_conversation_history("session-1")

    assert cleared is True
    redis_client.delete.assert_called_once()
