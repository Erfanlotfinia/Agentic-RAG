import json
import logging
from datetime import datetime, timezone

from .common import get_cached_services

logger = logging.getLogger(__name__)


def generate_daily_report(**context):
    """Generate an operational summary from completed ingestion tasks."""
    logger.info("Generating daily ingestion report")

    ti = context.get("ti")
    if not ti:
        logger.warning("No task instance available, generating basic report")
        return {"status": "basic_report", "message": "No task instance for XCom data"}

    fetch_stats = ti.xcom_pull(task_ids="fetch_daily_papers", key="fetch_results") or {}
    hybrid_stats = ti.xcom_pull(task_ids="index_papers_hybrid", key="hybrid_index_stats") or {}
    indexing_errors = int(hybrid_stats.get("total_errors", 0) or 0)
    papers_failed = int(hybrid_stats.get("papers_failed", 0) or 0)

    if not fetch_stats or not hybrid_stats:
        pipeline_status = "partial"
    elif indexing_errors > 0 or papers_failed > 0:
        pipeline_status = "failed"
    else:
        pipeline_status = "success"

    logical_date = context.get("logical_date") or context.get("data_interval_end") or datetime.now(timezone.utc)
    report = {
        "logical_date": logical_date.isoformat(),
        "fetch_statistics": {
            "papers_fetched": fetch_stats.get("papers_fetched", 0),
            "papers_stored": fetch_stats.get("papers_stored", 0),
            "target_date": fetch_stats.get("date", "unknown"),
        },
        "indexing_statistics": {
            "papers_processed": hybrid_stats.get("papers_processed", 0),
            "papers_failed": papers_failed,
            "chunks_created": hybrid_stats.get("total_chunks_created", 0),
            "chunks_indexed": hybrid_stats.get("total_chunks_indexed", 0),
            "embeddings_generated": hybrid_stats.get("total_embeddings_generated", 0),
            "errors": indexing_errors,
        },
        "pipeline_status": pipeline_status,
    }

    try:
        _arxiv_client, _pdf_parser, database, _metadata_fetcher, opensearch_client = get_cached_services()

        with database.get_session() as session:
            from sqlalchemy import func
            from src.models.paper import Paper

            total_papers = session.query(func.count(Paper.id)).scalar()
            report["database_statistics"] = {"total_papers": total_papers}

        if opensearch_client.health_check():
            try:
                stats_response = opensearch_client.client.indices.stats(index=opensearch_client.index_name)
                count_response = opensearch_client.client.count(index=opensearch_client.index_name)
                index_stats = stats_response["indices"][opensearch_client.index_name]["total"]

                report["opensearch_statistics"] = {
                    "index_name": opensearch_client.index_name,
                    "document_count": count_response["count"],
                    "index_size_mb": round(index_stats["store"]["size_in_bytes"] / (1024 * 1024), 2),
                }
            except Exception:
                logger.exception("Failed to collect OpenSearch statistics for ingestion report")
                report["opensearch_statistics"] = {
                    "index_name": opensearch_client.index_name,
                    "status": "unavailable",
                }
    except Exception:
        logger.exception("Failed to collect supplemental ingestion statistics")
        report["supplemental_statistics_status"] = "unavailable"

    logger.info("Daily ingestion report: %s", json.dumps(report, indent=2))
    ti.xcom_push(key="daily_report", value=report)
    return report
