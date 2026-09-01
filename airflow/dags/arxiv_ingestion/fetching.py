import asyncio
import logging
from datetime import datetime, timedelta, timezone

from src.config import get_settings

from .common import get_cached_services

logger = logging.getLogger(__name__)


def _resolve_target_date(context: dict) -> str:
    """Return the previous calendar date relative to the DAG data interval end."""
    data_interval_end = context.get("data_interval_end")
    reference_time = data_interval_end or datetime.now(timezone.utc)
    return (reference_time - timedelta(days=1)).strftime("%Y%m%d")


async def run_paper_ingestion_pipeline(target_date: str, process_pdfs: bool = True) -> dict:
    """Fetch/process one calendar day and expose source completeness metadata."""
    arxiv_client, _, database, metadata_fetcher, _ = get_cached_services()
    max_results = arxiv_client.max_results
    logger.info("Using configured daily ingestion cap: %s", max_results)

    with database.get_session() as session:
        results = await metadata_fetcher.fetch_and_process_papers(
            max_results=max_results,
            from_date=target_date,
            to_date=target_date,
            process_pdfs=process_pdfs,
            store_to_db=True,
            db_session=session,
        )

    available = arxiv_client.last_total_results
    results["available_results"] = available
    results["truncated"] = available is not None and int(results.get("papers_fetched", 0) or 0) < available
    return results


def fetch_daily_papers(**context):
    """Fetch the previous calendar day's arXiv papers and store them in PostgreSQL."""
    logger.info("Starting daily paper fetching task")
    target_date = _resolve_target_date(context)
    results = asyncio.run(run_paper_ingestion_pipeline(target_date=target_date, process_pdfs=True))

    results["date"] = target_date
    ti = context.get("ti")
    if ti:
        ti.xcom_push(key="fetch_results", value=results)

    fetched = int(results.get("papers_fetched", 0) or 0)
    stored = int(results.get("papers_stored", 0) or 0)
    available = results.get("available_results")
    logger.info(
        "Daily fetch attempt for %s: %s available, %s fetched, %s stored",
        target_date,
        available if available is not None else "unknown",
        fetched,
        stored,
    )

    if stored != fetched:
        raise RuntimeError(f"Incomplete PostgreSQL persistence for {target_date}: stored {stored} of {fetched} fetched papers")

    if results.get("truncated") and get_settings().arxiv.fail_on_truncation:
        raise RuntimeError(
            f"arXiv ingestion cap truncated {target_date}: fetched {fetched} of {available} available papers. "
            "Increase ARXIV__MAX_RESULTS or disable ARXIV__FAIL_ON_TRUNCATION only if bounded sampling is intentional."
        )

    return results
