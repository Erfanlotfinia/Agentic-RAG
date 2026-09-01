import asyncio
import hashlib
import json
import logging
from datetime import timedelta
from typing import List, Optional

import redis

from src.config import RedisSettings
from src.schemas.api.ask import AskRequest, AskResponse

logger = logging.getLogger(__name__)


class CacheClient:
    """Redis cache for exact RAG responses and bounded Agentic session history."""

    def __init__(self, redis_client: redis.Redis, settings: RedisSettings):
        self.redis = redis_client
        self.settings = settings
        self.ttl = timedelta(hours=settings.ttl_hours)

    def _generate_cache_key(self, request: AskRequest) -> str:
        key_data = {
            "query": request.query,
            "model": request.model,
            "top_k": request.top_k,
            "use_hybrid": request.use_hybrid,
            "categories": sorted(request.categories) if request.categories else [],
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        return f"exact_cache:{key_hash}"

    def _generate_session_key(self, session_id: str) -> str:
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()[:24]
        return f"agentic_session:{session_hash}"

    async def find_cached_response(self, request: AskRequest) -> Optional[AskResponse]:
        try:
            cached_response = await asyncio.to_thread(self.redis.get, self._generate_cache_key(request))
            if not cached_response:
                return None

            try:
                return AskResponse(**json.loads(cached_response))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning("Failed to deserialize cached response: %s", exc)
                return None
        except Exception as exc:
            logger.error("Error checking cache: %s", exc)
            return None

    async def store_response(self, request: AskRequest, response: AskResponse) -> bool:
        try:
            stored = await asyncio.to_thread(
                self.redis.set,
                self._generate_cache_key(request),
                response.model_dump_json(),
                ex=self.ttl,
            )
            return bool(stored)
        except Exception as exc:
            logger.error("Error storing response cache: %s", exc)
            return False

    async def get_conversation_history(self, session_id: str) -> List[dict]:
        """Load the bounded user/assistant history for an Agentic RAG session."""
        if not session_id:
            return []

        try:
            raw_items = await asyncio.to_thread(self.redis.lrange, self._generate_session_key(session_id), 0, -1)
            history = []
            for raw_item in raw_items:
                item = json.loads(raw_item)
                if isinstance(item, dict) and item.get("role") in {"user", "assistant"}:
                    history.append(item)
            return history
        except Exception as exc:
            logger.warning("Failed to load Agentic RAG session history: %s", exc)
            return []

    async def store_conversation_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        max_turns: int = 10,
    ) -> bool:
        """Atomically append one turn and retain only the latest bounded history."""
        if not session_id or max_turns < 1:
            return False

        key = self._generate_session_key(session_id)
        user_payload = json.dumps({"role": "user", "content": user_message}, ensure_ascii=False)
        assistant_payload = json.dumps({"role": "assistant", "content": assistant_message}, ensure_ascii=False)

        try:
            pipeline = self.redis.pipeline(transaction=True)
            pipeline.rpush(key, user_payload, assistant_payload)
            pipeline.ltrim(key, -(max_turns * 2), -1)
            pipeline.expire(key, self.ttl)
            results = await asyncio.to_thread(pipeline.execute)
            return bool(results and results[-1])
        except Exception as exc:
            logger.warning("Failed to store Agentic RAG session history: %s", exc)
            return False

    async def clear_conversation_history(self, session_id: str) -> bool:
        """Remove a stored Agentic RAG conversation."""
        if not session_id:
            return False
        try:
            deleted = await asyncio.to_thread(self.redis.delete, self._generate_session_key(session_id))
            return bool(deleted)
        except Exception as exc:
            logger.warning("Failed to clear Agentic RAG session history: %s", exc)
            return False
