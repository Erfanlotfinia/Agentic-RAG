import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from src.config import Settings
from src.exceptions import MetadataFetchingException, PipelineException
from src.repositories.paper import PaperRepository
from src.schemas.arxiv.paper import ArxivPaper, PaperCreate
from src.schemas.pdf_parser.models import ArxivMetadata, ParsedPaper
from src.services.arxiv.client import ArxivClient
from src.services.pdf_parser.parser import PDFParserService

logger = logging.getLogger(__name__)


class MetadataFetcher:
    """Service for fetching arXiv papers with PDF processing and database storage."""

    def __init__(
        self,
        arxiv_client: ArxivClient,
        pdf_parser: PDFParserService,
        pdf_cache_dir: Optional[Path] = None,
        max_concurrent_downloads: int = 5,
        max_concurrent_parsing: int = 3,
        settings: Optional[Settings] = None,
    ):
        from src.config import get_settings

        self.arxiv_client = arxiv_client
        self.pdf_parser = pdf_parser
        self.pdf_cache_dir = pdf_cache_dir or self.arxiv_client.pdf_cache_dir
        self.max_concurrent_downloads = max_concurrent_downloads
        self.max_concurrent_parsing = max_concurrent_parsing
        self.settings = settings or get_settings()

    async def fetch_and_process_papers(
        self,
        max_results: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        process_pdfs: bool = True,
        store_to_db: bool = True,
        db_session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Fetch papers, process PDFs, and optionally persist them."""
        results = {
            "papers_fetched": 0,
            "pdfs_downloaded": 0,
            "pdfs_parsed": 0,
            "papers_stored": 0,
            "stored_arxiv_ids": [],
            "papers_indexed": 0,
            "errors": [],
            "processing_time": 0,
        }

        start_time = datetime.now()

        try:
            papers = await self.arxiv_client.fetch_papers(
                max_results=max_results,
                from_date=from_date,
                to_date=to_date,
                sort_by="submittedDate",
                sort_order="descending",
            )
            results["papers_fetched"] = len(papers)

            if not papers:
                logger.info("No papers found for the requested source window")
                return results

            pdf_results = {}
            if process_pdfs:
                pdf_results = await self._process_pdfs_batch(papers)
                results["pdfs_downloaded"] = pdf_results["downloaded"]
                results["pdfs_parsed"] = pdf_results["parsed"]
                results["errors"].extend(pdf_results["errors"])

            if store_to_db and db_session:
                logger.info("Storing fetched papers in PostgreSQL")
                storage = self._store_papers_to_db(papers, pdf_results.get("parsed_papers", {}), db_session)
                results["papers_stored"] = storage["count"]
                results["stored_arxiv_ids"] = storage["arxiv_ids"]
                results["errors"].extend(storage["errors"])
            elif store_to_db:
                logger.warning("Database storage requested but no session provided")
                results["errors"].append("Database session not provided for storage")

            processing_time = (datetime.now() - start_time).total_seconds()
            results["processing_time"] = processing_time

            logger.info(
                "Pipeline completed in %.1fs: %s papers fetched, %s stored, %s PDFs downloaded, %s error(s)",
                processing_time,
                results["papers_fetched"],
                results["papers_stored"],
                results["pdfs_downloaded"],
                len(results["errors"]),
            )

            if results["errors"]:
                logger.warning("Ingestion produced %s non-fatal error(s)", len(results["errors"]))

            return results

        except Exception as e:
            logger.exception("Metadata pipeline failed")
            results["errors"].append(f"Pipeline error: {str(e)}")
            raise PipelineException(f"Pipeline execution failed: {e}") from e

    async def _process_pdfs_batch(self, papers: List[ArxivPaper]) -> Dict[str, Any]:
        """Download and parse PDFs with bounded concurrency."""
        results = {
            "downloaded": 0,
            "parsed": 0,
            "parsed_papers": {},
            "errors": [],
            "download_failures": [],
            "parse_failures": [],
        }

        logger.info("Starting PDF pipeline for %s papers", len(papers))
        download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
        parse_semaphore = asyncio.Semaphore(self.max_concurrent_parsing)
        pipeline_tasks = [self._download_and_parse_pipeline(paper, download_semaphore, parse_semaphore) for paper in papers]
        pipeline_results = await asyncio.gather(*pipeline_tasks, return_exceptions=True)

        for paper, result in zip(papers, pipeline_results):
            if isinstance(result, Exception):
                error_msg = f"Pipeline error for {paper.arxiv_id}: {str(result)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            elif result:
                if isinstance(result, tuple) and len(result) == 2:
                    download_success, parsed_paper = result
                else:
                    error_msg = f"Pipeline error for {paper.arxiv_id}: Unexpected result type {type(result).__name__}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
                    continue

                if download_success:
                    results["downloaded"] += 1
                    if parsed_paper:
                        results["parsed"] += 1
                        results["parsed_papers"][paper.arxiv_id] = parsed_paper
                    else:
                        results["parse_failures"].append(paper.arxiv_id)
                else:
                    results["download_failures"].append(paper.arxiv_id)
            else:
                results["download_failures"].append(paper.arxiv_id)

        logger.info("PDF processing: %s/%s downloaded, %s parsed", results["downloaded"], len(papers), results["parsed"])

        if results["download_failures"]:
            results["errors"].extend([f"Download failed: {arxiv_id}" for arxiv_id in results["download_failures"]])
        if results["parse_failures"]:
            results["errors"].extend([f"PDF parse failed: {arxiv_id}" for arxiv_id in results["parse_failures"]])

        return results

    async def _download_and_parse_pipeline(
        self, paper: ArxivPaper, download_semaphore: asyncio.Semaphore, parse_semaphore: asyncio.Semaphore
    ) -> tuple:
        """Download and parse one paper."""
        download_success = False
        parsed_paper = None

        try:
            async with download_semaphore:
                pdf_path = await self.arxiv_client.download_pdf(paper, False)
                if pdf_path:
                    download_success = True
                else:
                    logger.error("Download failed: %s", paper.arxiv_id)
                    return (False, None)

            async with parse_semaphore:
                pdf_content = await self.pdf_parser.parse_pdf(pdf_path)
                if pdf_content:
                    arxiv_metadata = ArxivMetadata(
                        title=paper.title,
                        authors=paper.authors,
                        abstract=paper.abstract,
                        arxiv_id=paper.arxiv_id,
                        categories=paper.categories,
                        published_date=paper.published_date,
                        pdf_url=paper.pdf_url,
                    )
                    parsed_paper = ParsedPaper(arxiv_metadata=arxiv_metadata, pdf_content=pdf_content)
                else:
                    logger.warning("PDF parsing failed for %s; metadata will still be stored", paper.arxiv_id)

        except Exception as e:
            logger.error("Pipeline error for %s: %s", paper.arxiv_id, e)
            raise MetadataFetchingException(f"Pipeline error for {paper.arxiv_id}: {e}") from e

        return (download_success, parsed_paper)

    def _serialize_parsed_content(self, parsed_paper: ParsedPaper) -> Dict[str, Any]:
        """Serialize parsed PDF content for database storage."""
        try:
            pdf_content = parsed_paper.pdf_content
            sections = [{"title": section.title, "content": section.content} for section in pdf_content.sections]
            references = list(pdf_content.references)
            return {
                "raw_text": pdf_content.raw_text,
                "sections": sections,
                "references": references,
                "parser_used": pdf_content.parser_used.value if pdf_content.parser_used else None,
                "parser_metadata": pdf_content.metadata or {},
                "pdf_processed": True,
                "pdf_processing_date": datetime.now(),
            }
        except Exception as e:
            logger.error("Failed to serialize parsed content: %s", e)
            return {"pdf_processed": False, "parser_metadata": {"error": str(e)}}

    def _store_papers_to_db(
        self,
        papers: List[ArxivPaper],
        parsed_papers: Dict[str, ParsedPaper],
        db_session: Session,
    ) -> Dict[str, Any]:
        """Store papers and return the exact identities committed by this run."""
        paper_repo = PaperRepository(db_session)
        stored_arxiv_ids: List[str] = []
        storage_errors: List[str] = []

        for paper in papers:
            try:
                parsed_paper = parsed_papers.get(paper.arxiv_id)
                published_date = (
                    date_parser.parse(paper.published_date) if isinstance(paper.published_date, str) else paper.published_date
                )
                paper_data = {
                    "arxiv_id": paper.arxiv_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "categories": paper.categories,
                    "published_date": published_date,
                    "pdf_url": paper.pdf_url,
                }

                if parsed_paper:
                    paper_data.update(self._serialize_parsed_content(parsed_paper))
                else:
                    paper_data.update(
                        {"pdf_processed": False, "parser_metadata": {"note": "PDF processing not available or failed"}}
                    )

                stored_paper = paper_repo.upsert(PaperCreate(**paper_data))
                if stored_paper:
                    stored_arxiv_ids.append(paper.arxiv_id)
                else:
                    storage_errors.append(f"Database upsert returned no paper for {paper.arxiv_id}")
            except Exception as e:
                logger.error("Failed to store paper %s: %s", paper.arxiv_id, e)
                storage_errors.append(f"Database storage failed for {paper.arxiv_id}")

        try:
            db_session.commit()
            logger.info("Committed %s papers to PostgreSQL", len(stored_arxiv_ids))
        except Exception:
            logger.exception("Failed to commit papers to PostgreSQL")
            db_session.rollback()
            storage_errors.append("Database commit failed")
            stored_arxiv_ids = []

        return {
            "count": len(stored_arxiv_ids),
            "arxiv_ids": stored_arxiv_ids,
            "errors": storage_errors,
        }


def make_metadata_fetcher(
    arxiv_client: ArxivClient,
    pdf_parser: PDFParserService,
    pdf_cache_dir: Optional[Path] = None,
    settings: Optional[Settings] = None,
) -> MetadataFetcher:
    """Create a configured MetadataFetcher."""
    from src.config import get_settings

    if settings is None:
        settings = get_settings()

    return MetadataFetcher(
        arxiv_client=arxiv_client,
        pdf_parser=pdf_parser,
        pdf_cache_dir=pdf_cache_dir,
        max_concurrent_downloads=settings.arxiv.max_concurrent_downloads,
        max_concurrent_parsing=settings.arxiv.max_concurrent_parsing,
        settings=settings,
    )
