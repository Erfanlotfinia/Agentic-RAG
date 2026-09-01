import logging

from fastapi import APIRouter, HTTPException
from src.dependencies import EmbeddingsDep, OpenSearchDep
from src.schemas.api.search import HybridSearchRequest, SearchHit, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hybrid-search", tags=["hybrid-search"])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    request: HybridSearchRequest, opensearch_client: OpenSearchDep, embeddings_service: EmbeddingsDep
) -> SearchResponse:
    """Search indexed chunks using BM25 or hybrid retrieval."""
    try:
        if not opensearch_client.health_check():
            raise HTTPException(status_code=503, detail="Search service is currently unavailable")

        # Newest-first ordering and relevance fusion are different contracts.
        # Explicit latest requests therefore use the BM25/date-sort path.
        effective_hybrid = request.use_hybrid and not request.latest_papers
        query_embedding = None
        if effective_hybrid:
            try:
                query_embedding = await embeddings_service.embed_query(request.query)
                logger.info("Generated query embedding for hybrid search")
            except Exception as exc:
                logger.warning("Failed to generate embeddings, falling back to BM25: %s", exc)

        effective_hybrid = effective_hybrid and query_embedding is not None
        logger.info("Search: %r (mode: %s)", request.query, "hybrid" if effective_hybrid else "bm25")

        results = opensearch_client.search_unified(
            query=request.query,
            query_embedding=query_embedding,
            size=request.size,
            from_=request.from_,
            categories=request.categories,
            latest=request.latest_papers,
            use_hybrid=effective_hybrid,
            min_score=request.min_score,
        )

        hits = []
        for hit in results.get("hits", []):
            hits.append(
                SearchHit(
                    arxiv_id=hit.get("arxiv_id", ""),
                    title=hit.get("title", ""),
                    authors=hit.get("authors"),
                    abstract=hit.get("abstract"),
                    published_date=hit.get("published_date"),
                    pdf_url=hit.get("pdf_url"),
                    score=hit.get("score", 0.0),
                    highlights=hit.get("highlights"),
                    chunk_text=hit.get("chunk_text"),
                    chunk_id=hit.get("chunk_id"),
                    section_name=hit.get("section_name"),
                )
            )

        search_response = SearchResponse(
            query=request.query,
            total=results.get("total", 0),
            hits=hits,
            size=request.size,
            **{"from": request.from_},
            search_mode="hybrid" if effective_hybrid else "bm25",
        )

        logger.info("Search completed: %s total matches", search_response.total)
        return search_response

    except HTTPException:
        raise
    except Exception:
        logger.exception("Search request failed")
        raise HTTPException(status_code=500, detail="Unable to execute the search request")
