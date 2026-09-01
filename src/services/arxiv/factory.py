from typing import Optional

from src.config import Settings, get_settings

from .client import ArxivClient


def make_arxiv_client(settings: Optional[Settings] = None) -> ArxivClient:
    """Create an arXiv client using the shared ingestion and PDF safety settings."""
    settings = settings or get_settings()
    return ArxivClient(
        settings=settings.arxiv,
        max_pdf_size_mb=settings.pdf_parser.max_file_size_mb,
    )
