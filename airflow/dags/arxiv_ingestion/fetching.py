import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from .common import get_cached_services

logger = logging.getLogger(__name__)


def _resolve_target_date(context: dict) -> str:
    """Return the previous calendar date relative to the DAG data interval end."""
    data_interval_end = context.get("data_interval_end")
    reference_time = data_interval_end or datetime.now(timezone.utc)
    return (reference_time - timedelta(days=1)).strftime("%Y%m%d")


async def run_paper_ingestion_pipeline(
    target_date: str,
    process_pdfs: bool = True,
) -> dict:
    """Async wrapper for the paper ingestion pipeline."""
    arxiv_client, _, database, metadata_fetcher, _ = get_cached_services()

    max_results = arxiv_client.max_results
    logger.info("Using configured max_results: %s", max_results)

    with database.get_session() as session:
        return await metadata_fetcher.fetch_and_process_papers(
            max_results=max_results,
            from_date=target_date,
            to_date=target_date,
            process_pdfs=process_pdfs,
            store_to_db=True,
            db_session=session,
        )


def fetch_daily_papers(**context):
    """Fetch the previous calendar day's arXiv papers and store them in PostgreSQL.

    Airflow's ``execution_date`` is the logical date (normally the start of the
    data interval), so the target is derived from ``data_interval_end`` instead
    of subtracting another day from the logical date.
    """
    logger.info("Starting daily paper fetching task")

    target_date = _resolve_target_date(context)
    logger.info("Fetching papers for date: %s", target_date)

    results = asyncio.run(
        run_paper_ingestion_pipeline(
            target_date=target_date,
            process_pdfs=True,
        )
    )

    results["date"] = target_date
    ti = context.get("ti")
    if ti:
        # Push the attempt details before raising so the all-done report task
        # can explain partial persistence and operators can inspect the IDs.
        ti.xcom_push(key="fetch_results", value=results)

    fetched = int(results.get("papers_fetched", 0) or 0)
    stored = int(results.get("papers_stored", 0) or 0)
    logger.info("Daily fetch attempt: %s fetched, %s stored for %s", fetched, stored, target_date)

    if stored != fetched:
        raise RuntimeError(
            f"Incomplete PostgreSQL persistence for {target_date}: stored {stored} of {fetched} fetched papers"
        )

    return results
