import logging
from typing import Optional

from src.config import get_settings
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.telegram.bot import TelegramBot

logger = logging.getLogger(__name__)


def make_telegram_service(
    opensearch_client,
    embeddings_client,
    agentic_rag_service: AgenticRAGService,
) -> Optional[TelegramBot]:
    """Create the optional Telegram bot using the shared Agentic RAG service."""
    settings = get_settings()

    if not settings.telegram.enabled:
        logger.info("Telegram bot is disabled")
        return None

    if not settings.telegram.bot_token:
        logger.warning("Telegram bot token not configured")
        return None

    return TelegramBot(
        bot_token=settings.telegram.bot_token,
        opensearch_client=opensearch_client,
        embeddings_client=embeddings_client,
        agentic_rag_service=agentic_rag_service,
    )
