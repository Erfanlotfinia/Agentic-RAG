import asyncio
import logging
from datetime import datetime, timedelta, timezone

from src.db.factory import make_database
from src.services.indexing.factory import make_hybrid_indexing_service
from src.services.opensearch.factory import make_opensearch_client_fresh

logger = logging.getLogger(__name__)


async def _index_papers_with_chunks(papers):
    """Index papers with safe replacement semantics and deterministic cleanup."""
    indexing_service = make_hybrid_indexing_service()
    try:
        papers_data = []
        for paper in papers:
            if hasattr(paper, "__dict__"):
                paper_dict = {
                    "id": str(paper.id),
                    "arxiv_id": paper.arxiv_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "categories": paper.categories,
                    "published_date": paper.published_date,
                    "raw_text": paper.raw_text,
                    "sections": paper.sections,
                }
            else:
                paper_dict = paper
            papers_data.append(paper_dict)

        return await indexing_service.index_papers_batch(papers=papers_data, replace_existing=True)
    finally:
        await indexing_service.close()


def _empty_stats() -> dict:
    return {
        "papers_processed": 0,
        "papers_failed": 0,
        "total_chunks_created": 0,
        "total_chunks_indexed": 0,
        "total_embeddings_generated": 0,
        "total_errors": 0,
    }


def index_papers_hybrid(**context):
    """Index the exact papers persisted by the upstream fetch task."""
    database = make_database()
    try:
        ti = context.get("ti")
        fetch_results = ti.xcom_pull(task_ids="fetch_daily_papers", key="fetch_results") if ti else None

        with database.get_session() as session:
            from src.models.paper import Paper

            if fetch_results is not None:
                stored_arxiv_ids = list(dict.fromkeys(fetch_results.get("stored_arxiv_ids", [])))
                expected_count = int(fetch_results.get("papers_stored", 0) or 0)

                if expected_count != len(stored_arxiv_ids):
                    raise RuntimeError(
                        "Fetch/index handoff is inconsistent: papers_stored does not match stored_arxiv_ids"
                    )

                if not stored_arxiv_ids:
                    logger.info("Fetch task stored no papers; nothing to index")
                    stats = _empty_stats()
                    if ti:
                        ti.xcom_push(key="hybrid_index_stats", value=stats)
                    return stats

                papers = session.query(Paper).filter(Paper.arxiv_id.in_(stored_arxiv_ids)).all()
                found_ids = {paper.arxiv_id for paper in papers}
                missing_ids = [arxiv_id for arxiv_id in stored_arxiv_ids if arxiv_id not in found_ids]
                if missing_ids:
                    raise RuntimeError(
                        f"Fetch/index handoff references {len(missing_ids)} paper(s) missing from PostgreSQL"
                    )
            else:
                # Manual/direct invocation fallback when no upstream Airflow XCom exists.
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=1)
                papers = session.query(Paper).filter(Paper.created_at >= cutoff_date).all()

            if not papers:
                logger.info("No papers to index for hybrid search")
                stats = _empty_stats()
                if ti:
                    ti.xcom_push(key="hybrid_index_stats", value=stats)
                return stats

            logger.info("Indexing %s exact paper(s) from the current ingestion handoff", len(papers))
            stats = asyncio.run(_index_papers_with_chunks(papers))

            if ti:
                ti.xcom_push(key="hybrid_index_stats", value=stats)

            logger.info(
                "Hybrid indexing attempt: %s papers, %s failed, %s chunks created, %s chunks indexed",
                stats["papers_processed"],
                stats["papers_failed"],
                stats["total_chunks_created"],
                stats["total_chunks_indexed"],
            )

            if stats["total_errors"] > 0 or stats["papers_failed"] > 0:
                raise RuntimeError(
                    f"Hybrid indexing incomplete: {stats['papers_failed']} paper(s) failed "
                    f"with {stats['total_errors']} indexing error(s)"
                )

            return stats
    except Exception:
        logger.exception("Failed to index papers for hybrid search")
        raise
    finally:
        database.teardown()


def verify_hybrid_index(**context):
    """Verify hybrid index health and get statistics."""
    opensearch_client = make_opensearch_client_fresh()
    try:
        stats = opensearch_client.client.indices.stats(index=opensearch_client.index_name)
        count = opensearch_client.client.count(index=opensearch_client.index_name)
        paper_count_query = {"aggs": {"unique_papers": {"cardinality": {"field": "arxiv_id"}}}, "size": 0}
        paper_count_response = opensearch_client.client.search(index=opensearch_client.index_name, body=paper_count_query)
        unique_papers = paper_count_response["aggregations"]["unique_papers"]["value"]

        result = {
            "index_name": opensearch_client.index_name,
            "total_chunks": count["count"],
            "unique_papers": unique_papers,
            "avg_chunks_per_paper": (count["count"] / unique_papers if unique_papers > 0 else 0),
            "index_size_mb": stats["indices"][opensearch_client.index_name]["total"]["store"]["size_in_bytes"] / (1024 * 1024),
        }

        logger.info(
            "Hybrid index stats: %s chunks, %s papers, %.1f chunks/paper",
            result["total_chunks"],
            result["unique_papers"],
            result["avg_chunks_per_paper"],
        )
        return result
    except Exception:
        logger.exception("Failed to verify hybrid index")
        raise
    finally:
        opensearch_client.close()
