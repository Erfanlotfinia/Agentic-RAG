import logging

from sqlalchemy import text

from .common import get_cached_services

logger = logging.getLogger(__name__)


def setup_environment():
    """Verify ingestion dependencies and ensure the retrieval index/pipeline exist."""
    logger.info("Setting up environment for arXiv paper ingestion")

    try:
        arxiv_client, _pdf_parser, database, _metadata_fetcher, opensearch_client = get_cached_services()

        with database.get_session() as session:
            session.execute(text("SELECT 1"))
            logger.info("Database connection verified")

        try:
            health = opensearch_client.client.cluster.health()
            cluster_status = health.get("status")
            if cluster_status not in {"green", "yellow"}:
                raise RuntimeError(f"OpenSearch cluster is not ready (status={cluster_status or 'unknown'})")
            logger.info("OpenSearch connected (cluster status: %s)", cluster_status)
        except Exception as exc:
            raise RuntimeError("OpenSearch connection/health verification failed") from exc

        setup_results = opensearch_client.setup_indices(force=False)
        if setup_results.get("hybrid_index"):
            logger.info("Hybrid search index created with vector support")
        else:
            logger.info("Hybrid search index already exists")

        if setup_results.get("rrf_pipeline"):
            logger.info("RRF search pipeline created successfully")
        else:
            logger.info("RRF search pipeline already exists")

        logger.info("arXiv connector configured for %s", arxiv_client.base_url)
        logger.info("PDF parser service initialized")

        return {"status": "success", "message": "Environment setup completed"}

    except Exception:
        logger.exception("Ingestion environment setup failed")
        raise
