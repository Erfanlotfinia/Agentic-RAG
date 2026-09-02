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
    redis_client.lrange.return_value = [
        json.dumps({"role": "user", "content": "What is attention?"}),
        json.dumps({"role": "assistant", "content": "Attention weights relevant tokens."}),
    ]

    history = await client.get_conversation_history("session-1")

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    redis_client.lrange.assert_called_once()
    assert redis_client.lrange.call_args.args[0].startswith("agentic_session:")


@pytest.mark.asyncio
async def test_store_conversation_turn_uses_atomic_bounded_pipeline(cache_client):
    client, redis_client = cache_client
    pipeline = Mock()
    pipeline.execute.return_value = [22, True, True]
    redis_client.pipeline.return_value = pipeline

    stored = await client.store_conversation_turn(
        session_id="session-1",
        user_message="latest question",
        assistant_message="latest answer",
        max_turns=10,
    )

    assert stored is True
    redis_client.pipeline.assert_called_once_with(transaction=True)

    key, user_payload, assistant_payload = pipeline.rpush.call_args.args
    assert key.startswith("agentic_session:")
    assert json.loads(user_payload) == {"role": "user", "content": "latest question"}
    assert json.loads(assistant_payload) == {"role": "assistant", "content": "latest answer"}
    pipeline.ltrim.assert_called_once_with(key, -20, -1)
    pipeline.expire.assert_called_once_with(key, client.ttl)
    pipeline.execute.assert_called_once_with()


@pytest.mark.asyncio
async def test_invalid_session_payload_fails_open(cache_client):
    client, redis_client = cache_client
    redis_client.lrange.return_value = ["not-json"]

    history = await client.get_conversation_history("session-1")

    assert history == []


@pytest.mark.asyncio
async def test_invalid_max_turns_is_rejected(cache_client):
    client, redis_client = cache_client

    stored = await client.store_conversation_turn(
        session_id="session-1",
        user_message="question",
        assistant_message="answer",
        max_turns=0,
    )

    assert stored is False
    redis_client.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_clear_conversation_history(cache_client):
    client, redis_client = cache_client
    redis_client.delete.return_value = 1

    cleared = await client.clear_conversation_history("session-1")

    assert cleared is True
    redis_client.delete.assert_called_once()
