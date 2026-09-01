from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import ArxivSettings
from src.exceptions import ArxivAPIException, ArxivAPITimeoutError, ArxivParseError, PDFDownloadException
from src.schemas.arxiv.paper import ArxivPaper
from src.services.arxiv.client import ArxivClient
from src.services.arxiv.factory import make_arxiv_client


def _feed(arxiv_id: str | None = None, total: int | None = None) -> str:
    total_xml = f"<opensearch:totalResults>{total}</opensearch:totalResults>" if total is not None else ""
    entry_xml = ""
    if arxiv_id:
        entry_xml = f"""
        <entry>
          <id>http://arxiv.org/abs/{arxiv_id}</id>
          <updated>2024-01-01T00:00:00Z</updated>
          <published>2024-01-01T00:00:00Z</published>
          <title>Test Paper {arxiv_id}</title>
          <summary>Test abstract content</summary>
          <author><name>Test Author</name></author>
          <category term="cs.AI"/>
          <link title="pdf" href="http://arxiv.org/pdf/{arxiv_id}" rel="alternate" type="application/pdf"/>
        </entry>
        """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
      {total_xml}
      {entry_xml}
    </feed>"""


class TestArxivClient:
    @pytest.fixture
    def arxiv_client(self, tmp_path):
        settings = ArxivSettings(
            base_url="https://export.arxiv.org/api/query",
            search_category="cs.AI",
            max_results=10,
            page_size=10,
            rate_limit_delay=0,
            timeout_seconds=5,
            pdf_cache_dir=str(tmp_path),
        )
        return ArxivClient(settings, max_pdf_size_mb=1)

    def test_factory_creates_client(self):
        client = make_arxiv_client()
        assert isinstance(client, ArxivClient)
        assert client.search_category == "cs.AI"
        # pytest loads .env.test, which intentionally keeps ingestion small.
        assert client.max_results == 15

    @pytest.mark.asyncio
    async def test_fetch_papers_success(self, arxiv_client):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = _feed("2024.0001v1", total=1)
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            papers = await arxiv_client.fetch_papers(max_results=1)

        assert len(papers) == 1
        assert papers[0].arxiv_id == "2024.0001v1"
        assert papers[0].authors == ["Test Author"]
        assert papers[0].categories == ["cs.AI"]
        assert arxiv_client.last_total_results == 1

    @pytest.mark.asyncio
    async def test_fetch_papers_paginates_to_requested_cap(self, tmp_path):
        settings = ArxivSettings(
            max_results=2,
            page_size=1,
            rate_limit_delay=0,
            pdf_cache_dir=str(tmp_path),
        )
        client = ArxivClient(settings)
        response_one = MagicMock(text=_feed("2024.0001v1", total=2))
        response_two = MagicMock(text=_feed("2024.0002v1", total=2))
        response_one.raise_for_status.return_value = None
        response_two.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[response_one, response_two])
            papers = await client.fetch_papers(max_results=2)

        assert [paper.arxiv_id for paper in papers] == ["2024.0001v1", "2024.0002v1"]
        assert client.last_total_results == 2
        calls = mock_client.return_value.__aenter__.return_value.get.call_args_list
        assert "start=0" in calls[0].args[0]
        assert "start=1" in calls[1].args[0]

    @pytest.mark.asyncio
    async def test_fetch_papers_with_date_filters(self, arxiv_client):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock(text=_feed("2024.0001v1", total=1))
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            await arxiv_client.fetch_papers(max_results=1, from_date="20240101", to_date="20240131")
            call_url = mock_client.return_value.__aenter__.return_value.get.call_args.args[0]
        assert "submittedDate:[202401010000+TO+202401312359]" in call_url

    @pytest.mark.asyncio
    async def test_fetch_papers_http_timeout(self, arxiv_client):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            with pytest.raises(ArxivAPITimeoutError, match="arXiv API request timed out"):
                await arxiv_client.fetch_papers(max_results=1)

    @pytest.mark.asyncio
    async def test_fetch_papers_http_error(self, arxiv_client):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock(status_code=500)
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
            )
            with pytest.raises(ArxivAPIException, match="arXiv API returned error 500"):
                await arxiv_client.fetch_papers(max_results=1)

    @pytest.mark.asyncio
    async def test_fetch_paper_by_id_success(self, arxiv_client):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock(text=_feed("2024.0001v1", total=1))
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            paper = await arxiv_client.fetch_paper_by_id("2024.0001v1")
        assert paper is not None
        assert paper.arxiv_id == "2024.0001v1"

    @pytest.mark.asyncio
    async def test_fetch_paper_by_id_not_found(self, arxiv_client):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock(text=_feed(total=0))
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            paper = await arxiv_client.fetch_paper_by_id("nonexistent")
        assert paper is None

    def test_parse_response_invalid_xml(self, arxiv_client):
        with pytest.raises(ArxivParseError, match="Failed to parse arXiv XML response"):
            arxiv_client._parse_response("not xml")

    @pytest.mark.asyncio
    async def test_download_pdf_cached(self, arxiv_client):
        paper = ArxivPaper(
            arxiv_id="2024.0001v1",
            title="Test Paper",
            authors=["Test Author"],
            abstract="Test abstract",
            categories=["cs.AI"],
            published_date="2024-01-01T00:00:00Z",
            pdf_url="https://arxiv.org/pdf/2024.0001v1",
        )
        cached = arxiv_client._get_pdf_path(paper.arxiv_id)
        cached.write_bytes(b"cached")
        assert await arxiv_client.download_pdf(paper) == cached

    @pytest.mark.asyncio
    async def test_download_rejects_oversized_content_before_cache_commit(self, arxiv_client):
        target = arxiv_client.pdf_cache_dir / "oversized.pdf"
        response = MagicMock()
        response.headers = {"content-length": str(2 * 1024 * 1024)}
        response.raise_for_status.return_value = None
        stream_context = MagicMock()
        stream_context.__aenter__ = AsyncMock(return_value=response)
        stream_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_client:
            client = mock_client.return_value.__aenter__.return_value
            client.stream.return_value = stream_context
            with pytest.raises(PDFDownloadException, match="exceeds configured download limit"):
                await arxiv_client._download_with_retry("https://arxiv.org/pdf/test", target, max_retries=1)

        assert not target.exists()
        assert not target.with_suffix(".pdf.part").exists()

    def test_rate_limiting_configuration(self, arxiv_client):
        assert arxiv_client.rate_limit_delay == 0
