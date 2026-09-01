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

        # Date sorting and relevance fusion express different ordering semantics.
        # When callers explicitly request latest papers, honor that request with
        # the BM25/date-sort path instead of silently ignoring latest_papers.
        effective_hybrid = request.use_hybrid and not request.latest_papers
        query_embedding = None
        if effective_hybrid:
            try:
                query_embedding = await embeddings_service.embed_query(request.query)
                logger.info("Generated query embedding for hybrid search")
            except Exception as e:
                logger.warning(f"Failed to generate embeddings, falling back to BM25: {e}")

        effective_hybrid = effective_hybrid and query_embedding is not None

        # The OpenSearch hybrid helper currently ranks from offset zero. Fetch
        # enough ranked candidates to honor the requested API offset, then slice
        # the page here. BM25 supports native from/size pagination directly.
        retrieval_size = request.size + request.from_ if effective_hybrid else request.size
        retrieval_from = 0 if effective_hybrid else request.from_

        logger.info("Search: %r (mode: %s)", request.query, "hybrid" if effective_hybrid else "bm25")

        results = opensearch_client.search_unified(
            query=request.query,
            query_embedding=query_embedding,
            size=retrieval_size,
            from_=retrieval_from,
            categories=request.categories,
            latest=request.latest_papers,
            use_hybrid=effective_hybrid,
            min_score=request.min_score,
        )

        result_hits = results.get("hits", [])
        if effective_hybrid and request.from_:
            result_hits = result_hits[request.from_ : request.from_ + request.size]
        else:
            result_hits = result_hits[: request.size]

        hits = []
        for hit in result_hits:
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

        logger.info("Search completed: %s results reported", search_response.total)
        return search_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hybrid search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
