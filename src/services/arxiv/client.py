import asyncio
import logging
import os
import time
import xml.etree.ElementTree as ET
from functools import cached_property
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote, urlencode

import httpx
from src.config import ArxivSettings
from src.exceptions import ArxivAPIException, ArxivAPITimeoutError, ArxivParseError, PDFDownloadException, PDFDownloadTimeoutError
from src.schemas.arxiv.paper import ArxivPaper

logger = logging.getLogger(__name__)


class ArxivClient:
    """Rate-limited arXiv client with bounded pagination and safe PDF caching."""

    def __init__(self, settings: ArxivSettings, max_pdf_size_mb: int = 20):
        self._settings = settings
        self._last_request_time: Optional[float] = None
        self._last_total_results: Optional[int] = None
        self.max_pdf_size_bytes = max_pdf_size_mb * 1024 * 1024

    @cached_property
    def pdf_cache_dir(self) -> Path:
        cache_dir = Path(self._settings.pdf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @property
    def base_url(self) -> str:
        return self._settings.base_url

    @property
    def namespaces(self) -> dict:
        return self._settings.namespaces

    @property
    def rate_limit_delay(self) -> float:
        return self._settings.rate_limit_delay

    @property
    def timeout_seconds(self) -> int:
        return self._settings.timeout_seconds

    @property
    def max_results(self) -> int:
        return self._settings.max_results

    @property
    def search_category(self) -> str:
        return self._settings.search_category

    @property
    def last_total_results(self) -> Optional[int]:
        """Total matches reported by arXiv for the most recent paginated query."""
        return self._last_total_results

    async def _respect_rate_limit(self) -> None:
        if self._last_request_time is not None:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.monotonic()

    async def _get_text(self, url: str) -> str:
        await self._respect_rate_limit()
        try:
            async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException as exc:
            raise ArxivAPITimeoutError(f"arXiv API request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ArxivAPIException(f"arXiv API returned error {exc.response.status_code}: {exc}") from exc
        except ArxivAPIException:
            raise
        except Exception as exc:
            raise ArxivAPIException(f"Unexpected error fetching papers from arXiv: {exc}") from exc

    def _build_query_url(
        self,
        search_query: str,
        start: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> str:
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": page_size,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        return f"{self.base_url}?{urlencode(params, quote_via=quote, safe=':+[]*')}"

    def _parse_total_results(self, xml_data: str) -> Optional[int]:
        try:
            root = ET.fromstring(xml_data)
            value = root.find("opensearch:totalResults", self.namespaces)
            if value is None or value.text is None:
                return None
            return int(value.text.strip())
        except (ET.ParseError, TypeError, ValueError):
            return None

    async def _fetch_query_paginated(
        self,
        search_query: str,
        max_results: int,
        start: int,
        sort_by: str,
        sort_order: str,
    ) -> List[ArxivPaper]:
        papers: List[ArxivPaper] = []
        seen_ids: set[str] = set()
        offset = start
        self._last_total_results = None

        while len(papers) < max_results:
            page_size = min(self._settings.page_size, max_results - len(papers), 2000)
            xml_data = await self._get_text(self._build_query_url(search_query, offset, page_size, sort_by, sort_order))

            if self._last_total_results is None:
                self._last_total_results = self._parse_total_results(xml_data)
                if (
                    self._settings.fail_on_truncation
                    and self._last_total_results is not None
                    and self._last_total_results > max_results
                ):
                    raise ArxivAPIException(
                        f"arXiv query has {self._last_total_results} matches, exceeding configured cap {max_results}. "
                        "Increase ARXIV__MAX_RESULTS or explicitly disable ARXIV__FAIL_ON_TRUNCATION for bounded sampling."
                    )

            page = self._parse_response(xml_data)
            if not page:
                break

            for paper in page:
                if paper.arxiv_id not in seen_ids:
                    papers.append(paper)
                    seen_ids.add(paper.arxiv_id)
                    if len(papers) >= max_results:
                        break

            offset += len(page)
            if len(page) < page_size:
                break
            if self._last_total_results is not None and offset >= self._last_total_results:
                break

        logger.info(
            "Fetched %s arXiv papers (reported total=%s, configured cap=%s)",
            len(papers),
            self._last_total_results if self._last_total_results is not None else "unknown",
            max_results,
        )
        return papers

    async def fetch_papers(
        self,
        max_results: Optional[int] = None,
        start: int = 0,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[ArxivPaper]:
        """Fetch up to ``max_results`` papers, transparently paging the arXiv API."""
        requested_max = max_results if max_results is not None else self.max_results
        search_query = f"cat:{self.search_category}"
        if from_date or to_date:
            date_from = f"{from_date}0000" if from_date else "*"
            date_to = f"{to_date}2359" if to_date else "*"
            search_query += f" AND submittedDate:[{date_from}+TO+{date_to}]"
        return await self._fetch_query_paginated(search_query, requested_max, start, sort_by, sort_order)

    async def fetch_papers_with_query(
        self,
        search_query: str,
        max_results: Optional[int] = None,
        start: int = 0,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> List[ArxivPaper]:
        """Fetch a custom arXiv query with the same bounded pagination contract."""
        requested_max = max_results if max_results is not None else self.max_results
        return await self._fetch_query_paginated(search_query, requested_max, start, sort_by, sort_order)

    async def fetch_paper_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
        params = {"id_list": clean_id, "max_results": 1}
        url = f"{self.base_url}?{urlencode(params, quote_via=quote, safe=':+[]*')}"
        xml_data = await self._get_text(url)
        papers = self._parse_response(xml_data)
        if papers:
            return papers[0]
        logger.warning("Paper %s not found", arxiv_id)
        return None

    def _parse_response(self, xml_data: str) -> List[ArxivPaper]:
        try:
            root = ET.fromstring(xml_data)
            papers = []
            for entry in root.findall("atom:entry", self.namespaces):
                paper = self._parse_single_entry(entry)
                if paper:
                    papers.append(paper)
            return papers
        except ET.ParseError as exc:
            raise ArxivParseError(f"Failed to parse arXiv XML response: {exc}") from exc
        except Exception as exc:
            raise ArxivParseError(f"Unexpected error parsing arXiv response: {exc}") from exc

    def _parse_single_entry(self, entry: ET.Element) -> Optional[ArxivPaper]:
        try:
            arxiv_id = self._get_arxiv_id(entry)
            if not arxiv_id:
                return None
            return ArxivPaper(
                arxiv_id=arxiv_id,
                title=self._element_text(entry, "atom:title", clean_newlines=True),
                authors=self._get_authors(entry),
                abstract=self._element_text(entry, "atom:summary", clean_newlines=True),
                published_date=self._element_text(entry, "atom:published"),
                categories=self._get_categories(entry),
                pdf_url=self._get_pdf_url(entry),
            )
        except Exception as exc:
            logger.error("Failed to parse arXiv entry: %s", exc)
            return None

    def _element_text(self, element: ET.Element, path: str, clean_newlines: bool = False) -> str:
        child = element.find(path, self.namespaces)
        if child is None or child.text is None:
            return ""
        text = child.text.strip()
        return text.replace("\n", " ") if clean_newlines else text

    def _get_arxiv_id(self, entry: ET.Element) -> Optional[str]:
        id_elem = entry.find("atom:id", self.namespaces)
        if id_elem is None or id_elem.text is None:
            return None
        return id_elem.text.split("/")[-1]

    def _get_authors(self, entry: ET.Element) -> List[str]:
        return [
            name
            for author in entry.findall("atom:author", self.namespaces)
            if (name := self._element_text(author, "atom:name"))
        ]

    def _get_categories(self, entry: ET.Element) -> List[str]:
        return [term for category in entry.findall("atom:category", self.namespaces) if (term := category.get("term"))]

    def _get_pdf_url(self, entry: ET.Element) -> str:
        for link in entry.findall("atom:link", self.namespaces):
            if link.get("type") == "application/pdf":
                url = link.get("href", "")
                if url.startswith("http://arxiv.org/"):
                    return url.replace("http://arxiv.org/", "https://arxiv.org/")
                return url
        return ""

    async def download_pdf(self, paper: ArxivPaper, force_download: bool = False) -> Optional[Path]:
        """Download a PDF atomically into the local cache with a hard byte limit."""
        if not paper.pdf_url:
            logger.error("No PDF URL for paper %s", paper.arxiv_id)
            return None

        pdf_path = self._get_pdf_path(paper.arxiv_id)
        if pdf_path.exists() and not force_download:
            return pdf_path

        return pdf_path if await self._download_with_retry(paper.pdf_url, pdf_path) else None

    def _get_pdf_path(self, arxiv_id: str) -> Path:
        return self.pdf_cache_dir / (arxiv_id.replace("/", "_") + ".pdf")

    def _cleanup_partial(self, partial_path: Path) -> None:
        try:
            partial_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove partial PDF %s", partial_path.name)

    async def _download_with_retry(self, url: str, path: Path, max_retries: Optional[int] = None) -> bool:
        retries = max_retries if max_retries is not None else self._settings.download_max_retries
        partial_path = path.with_suffix(path.suffix + ".part")

        for attempt in range(retries):
            self._cleanup_partial(partial_path)
            try:
                await self._respect_rate_limit()
                async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > self.max_pdf_size_bytes:
                            raise PDFDownloadException(
                                f"PDF exceeds configured download limit of {self.max_pdf_size_bytes // (1024 * 1024)} MB"
                            )

                        bytes_written = 0
                        with partial_path.open("wb") as handle:
                            async for chunk in response.aiter_bytes():
                                bytes_written += len(chunk)
                                if bytes_written > self.max_pdf_size_bytes:
                                    raise PDFDownloadException(
                                        f"PDF exceeds configured download limit of {self.max_pdf_size_bytes // (1024 * 1024)} MB"
                                    )
                                handle.write(chunk)

                os.replace(partial_path, path)
                logger.info("Downloaded PDF %s (%s bytes)", path.name, bytes_written)
                return True

            except PDFDownloadException:
                self._cleanup_partial(partial_path)
                raise
            except httpx.TimeoutException as exc:
                self._cleanup_partial(partial_path)
                if attempt >= retries - 1:
                    raise PDFDownloadTimeoutError(f"PDF download timed out after {retries} attempts: {exc}") from exc
            except httpx.HTTPError as exc:
                self._cleanup_partial(partial_path)
                if attempt >= retries - 1:
                    raise PDFDownloadException(f"PDF download failed after {retries} attempts: {exc}") from exc
            except Exception as exc:
                self._cleanup_partial(partial_path)
                raise PDFDownloadException(f"Unexpected error during PDF download: {exc}") from exc

            wait_time = self._settings.download_retry_delay_base * (attempt + 1)
            logger.warning("PDF download attempt %s/%s failed; retrying", attempt + 1, retries)
            if wait_time:
                await asyncio.sleep(wait_time)

        return False
