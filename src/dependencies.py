from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, Generator, Optional

if TYPE_CHECKING:
    from fastapi import Depends, Request
    from sqlalchemy.orm import Session
else:
    try:
        from fastapi import Depends, Request
        from sqlalchemy.orm import Session
    except ImportError:
        pass

from src.config import Settings
from src.db.interfaces.base import BaseDatabase
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.arxiv.client import ArxivClient
from src.services.cache.client import CacheClient
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient
from src.services.pdf_parser.parser import PDFParserService
from src.services.telegram.bot import TelegramBot


@lru_cache
def get_settings() -> Settings:
    """Construct settings for compatibility with non-request callers."""
    return Settings()


def get_request_settings(request: Request) -> Settings:
    """Return the same immutable settings object initialized by app lifespan."""
    return request.app.state.settings


def get_database(request: Request) -> BaseDatabase:
    return request.app.state.database


def get_db_session(database: Annotated[BaseDatabase, Depends(get_database)]) -> Generator[Session, None, None]:
    with database.get_session() as session:
        yield session


def get_opensearch_client(request: Request) -> OpenSearchClient:
    return request.app.state.opensearch_client


def get_arxiv_client(request: Request) -> ArxivClient:
    return request.app.state.arxiv_client


def get_pdf_parser(request: Request) -> PDFParserService:
    return request.app.state.pdf_parser


def get_embeddings_service(request: Request) -> JinaEmbeddingsClient:
    return request.app.state.embeddings_service


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.ollama_client


def get_langfuse_tracer(request: Request) -> LangfuseTracer:
    return request.app.state.langfuse_tracer


def get_cache_client(request: Request) -> CacheClient | None:
    return getattr(request.app.state, "cache_client", None)


def get_telegram_service(request: Request) -> Optional[TelegramBot]:
    return getattr(request.app.state, "telegram_service", None)


def get_agentic_rag_service(request: Request) -> AgenticRAGService:
    """Return the shared service so graph/checkpoint state can survive across API requests."""
    return request.app.state.agentic_rag_service


SettingsDep = Annotated[Settings, Depends(get_request_settings)]
DatabaseDep = Annotated[BaseDatabase, Depends(get_database)]
SessionDep = Annotated[Session, Depends(get_db_session)]
OpenSearchDep = Annotated[OpenSearchClient, Depends(get_opensearch_client)]
ArxivDep = Annotated[ArxivClient, Depends(get_arxiv_client)]
PDFParserDep = Annotated[PDFParserService, Depends(get_pdf_parser)]
EmbeddingsDep = Annotated[JinaEmbeddingsClient, Depends(get_embeddings_service)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama_client)]
LangfuseDep = Annotated[LangfuseTracer, Depends(get_langfuse_tracer)]
CacheDep = Annotated[CacheClient | None, Depends(get_cache_client)]
TelegramDep = Annotated[Optional[TelegramBot], Depends(get_telegram_service)]
AgenticRAGDep = Annotated[AgenticRAGService, Depends(get_agentic_rag_service)]
