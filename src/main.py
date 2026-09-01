import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.config import get_settings
from src.db.factory import make_database
from src.routers import agentic_ask, hybrid_search, ping
from src.routers.ask import ask_router, stream_router
from src.services.agents.factory import make_agentic_rag_service
from src.services.arxiv.factory import make_arxiv_client
from src.services.cache.factory import make_cache_client
from src.services.embeddings.factory import make_embeddings_service
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.factory import make_ollama_client
from src.services.opensearch.factory import make_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service
from src.services.telegram.factory import make_telegram_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down application-scoped services."""
    logger.info("Starting RAG API...")

    settings = get_settings()
    app.state.settings = settings

    database = make_database()
    app.state.database = database
    logger.info("Database connected")

    opensearch_client = make_opensearch_client()
    app.state.opensearch_client = opensearch_client

    if opensearch_client.health_check():
        logger.info("OpenSearch connected successfully")
        setup_results = opensearch_client.setup_indices(force=False)
        if setup_results.get("hybrid_index"):
            logger.info("Hybrid index created")
        else:
            logger.info("Hybrid index already exists")
        try:
            stats = opensearch_client.client.count(index=opensearch_client.index_name)
            logger.info("OpenSearch ready: %s documents indexed", stats["count"])
        except Exception:
            logger.info("OpenSearch index ready (stats unavailable)")
    else:
        logger.warning("OpenSearch connection failed - search features will be limited")

    app.state.arxiv_client = make_arxiv_client()
    app.state.pdf_parser = make_pdf_parser_service()
    app.state.embeddings_service = make_embeddings_service()
    app.state.ollama_client = make_ollama_client()
    app.state.langfuse_tracer = make_langfuse_tracer()
    app.state.cache_client = make_cache_client(settings)

    app.state.agentic_rag_service = make_agentic_rag_service(
        opensearch_client=app.state.opensearch_client,
        ollama_client=app.state.ollama_client,
        embeddings_client=app.state.embeddings_service,
        langfuse_tracer=app.state.langfuse_tracer,
        cache_client=app.state.cache_client,
        model=settings.ollama_model,
    )
    logger.info("Core RAG and Agentic RAG services initialized")

    telegram_service = make_telegram_service(
        opensearch_client=app.state.opensearch_client,
        embeddings_client=app.state.embeddings_service,
        agentic_rag_service=app.state.agentic_rag_service,
    )

    if telegram_service:
        app.state.telegram_service = telegram_service
        try:
            await telegram_service.start()
            logger.info("Telegram bot started successfully")
        except Exception as exc:
            logger.error("Failed to start Telegram bot: %s", exc)
    else:
        logger.info("Telegram bot not configured - skipping initialization")

    logger.info("API ready")
    yield

    if hasattr(app.state, "telegram_service") and app.state.telegram_service:
        await app.state.telegram_service.stop()
        logger.info("Telegram bot stopped")

    try:
        await app.state.embeddings_service.close()
    except Exception:
        logger.debug("Embeddings client cleanup skipped", exc_info=True)

    if app.state.langfuse_tracer:
        app.state.langfuse_tracer.shutdown()

    database.teardown()
    logger.info("API shutdown complete")


app = FastAPI(
    title="arXiv Paper Curator API",
    description="Personal arXiv CS.AI paper curator with RAG capabilities",
    version=os.getenv("APP_VERSION", "0.1.0"),
    lifespan=lifespan,
)

app.include_router(ping.router, prefix="/api/v1")
app.include_router(hybrid_search.router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(agentic_ask.router)


if __name__ == "__main__":
    uvicorn.run(app, port=8000, host="0.0.0.0")
