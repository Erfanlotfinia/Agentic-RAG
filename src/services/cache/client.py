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
    """Redis cache for exact RAG responses and Agentic RAG session history."""

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
            cached_response = self.redis.get(self._generate_cache_key(request))
            if not cached_response:
                return None

            try:
                return AskResponse(**json.loads(cached_response))
            except json.JSONDecodeError as exc:
                logger.warning("Failed to deserialize cached response: %s", exc)
                return None
        except Exception as exc:
            logger.error("Error checking cache: %s", exc)
            return None

    async def store_response(self, request: AskRequest, response: AskResponse) -> bool:
        try:
            return bool(
                self.redis.set(
                    self._generate_cache_key(request),
                    response.model_dump_json(),
                    ex=self.ttl,
                )
            )
        except Exception as exc:
            logger.error("Error storing response cache: %s", exc)
            return False

    async def get_conversation_history(self, session_id: str) -> List[dict]:
        """Load the bounded user/assistant history for an Agentic RAG session."""
        if not session_id:
            return []
        try:
            raw = self.redis.get(self._generate_session_key(session_id))
            if not raw:
                return []
            payload = json.loads(raw)
            return payload if isinstance(payload, list) else []
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
        """Append one turn and keep the latest bounded history in shared Redis."""
        if not session_id:
            return False

        try:
            history = await self.get_conversation_history(session_id)
            history.extend(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message},
                ]
            )
            history = history[-(max_turns * 2) :]
            return bool(
                self.redis.set(
                    self._generate_session_key(session_id),
                    json.dumps(history, ensure_ascii=False),
                    ex=self.ttl,
                )
            )
        except Exception as exc:
            logger.warning("Failed to store Agentic RAG session history: %s", exc)
            return False

    async def clear_conversation_history(self, session_id: str) -> bool:
        """Remove a stored Agentic RAG conversation."""
        if not session_id:
            return False
        try:
            return bool(self.redis.delete(self._generate_session_key(session_id)))
        except Exception as exc:
            logger.warning("Failed to clear Agentic RAG session history: %s", exc)
            return False
