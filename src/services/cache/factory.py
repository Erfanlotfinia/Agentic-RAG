import logging

import redis
from src.config import Settings
from src.services.cache.client import CacheClient

logger = logging.getLogger(__name__)


def make_redis_client(settings: Settings) -> redis.Redis:
    """Create a lazy Redis client; connectivity is handled by fail-open cache/session operations."""
    redis_settings = settings.redis
    client = redis.Redis(
        host=redis_settings.host,
        port=redis_settings.port,
        password=redis_settings.password if redis_settings.password else None,
        db=redis_settings.db,
        decode_responses=redis_settings.decode_responses,
        socket_timeout=redis_settings.socket_timeout,
        socket_connect_timeout=redis_settings.socket_connect_timeout,
        retry_on_timeout=True,
        retry_on_error=[redis.ConnectionError, redis.TimeoutError],
    )
    logger.info("Redis client initialized for %s:%s", redis_settings.host, redis_settings.port)
    return client


def make_cache_client(settings: Settings) -> CacheClient:
    """Create the fail-open response cache and Agentic session client."""
    return CacheClient(make_redis_client(settings), settings.redis)
