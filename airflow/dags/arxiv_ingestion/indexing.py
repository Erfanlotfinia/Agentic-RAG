import asyncio
import logging
from datetime import datetime, timedelta, timezone

from src.db.factory import make_database
from src.services.indexing.factory import make_hybrid_indexing_service
from src.services.opensearch.factory import make_opensearch_client_fresh

logger = logging.getLogger(__name__)


async def _index_papers_with_chunks(papers):
    """Async helper to index papers with safe replacement semantics."""
    indexing_service = make_hybrid_indexing_service()

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


def index_papers_hybrid(**context):
    """Index recently ingested papers with chunking and vector embeddings."""
    try:
        database = make_database()
        ti = context.get("ti")
        fetch_results = ti.xcom_pull(task_ids="fetch_daily_papers", key="fetch_results") if ti else None

        with database.get_session() as session:
            from src.models.paper import Paper

            if fetch_results and fetch_results.get("papers_stored", 0) > 0:
                from sqlalchemy import desc

                papers = session.query(Paper).order_by(desc(Paper.created_at)).limit(fetch_results["papers_stored"]).all()
            else:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=1)
                papers = session.query(Paper).filter(Paper.created_at >= cutoff_date).all()

            if not papers:
                logger.info("No papers to index for hybrid search")
                stats = {
                    "papers_processed": 0,
                    "papers_failed": 0,
                    "total_chunks_created": 0,
                    "total_chunks_indexed": 0,
                    "total_embeddings_generated": 0,
                    "total_errors": 0,
                }
                if ti:
                    ti.xcom_push(key="hybrid_index_stats", value=stats)
                return stats

            logger.info("Indexing %s papers for hybrid search", len(papers))
            stats = asyncio.run(_index_papers_with_chunks(papers))

            if ti:
                # Persist failure statistics before raising so retries/operators
                # can inspect exactly what happened in this attempt.
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
