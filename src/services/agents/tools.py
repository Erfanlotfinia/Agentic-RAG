import json
import logging
from typing import List, Optional

from langchain_core.tools import tool

from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.opensearch.client import OpenSearchClient

logger = logging.getLogger(__name__)


def _normalize_authors(authors) -> List[str]:
    if isinstance(authors, list):
        return [str(author) for author in authors]
    if isinstance(authors, str):
        return [author.strip() for author in authors.split(",") if author.strip()]
    return []


def _paper_url(arxiv_id: str) -> str:
    clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
    return f"https://arxiv.org/pdf/{clean_id}.pdf"


def create_retriever_tool(
    opensearch_client: OpenSearchClient,
    embeddings_client: JinaEmbeddingsClient,
    top_k: int = 3,
    use_hybrid: bool = True,
    categories: Optional[List[str]] = None,
):
    """Create the LangGraph retriever tool around the shared OpenSearch service."""

    @tool
    async def retrieve_papers(query: str) -> str:
        """Search and return relevant arXiv research paper chunks with source metadata."""
        logger.info("Retrieving papers for query: %s", query[:100])

        query_embedding = None
        effective_hybrid = use_hybrid
        if use_hybrid:
            try:
                query_embedding = await embeddings_client.embed_query(query)
            except Exception as exc:
                logger.warning("Query embedding failed; falling back to BM25: %s", exc)
                effective_hybrid = False

        search_results = opensearch_client.search_unified(
            query=query,
            query_embedding=query_embedding,
            size=top_k,
            categories=categories,
            use_hybrid=effective_hybrid,
        )

        search_mode = "hybrid" if effective_hybrid and query_embedding is not None else "bm25"
        documents = []
        for hit in search_results.get("hits", []):
            arxiv_id = hit.get("arxiv_id", "")
            documents.append(
                {
                    "page_content": hit.get("chunk_text", hit.get("abstract", "")),
                    "metadata": {
                        "arxiv_id": arxiv_id,
                        "title": hit.get("title", ""),
                        "authors": _normalize_authors(hit.get("authors")),
                        "score": float(hit.get("score", 0.0) or 0.0),
                        "source": _paper_url(arxiv_id) if arxiv_id else "",
                        "section": hit.get("section_name", hit.get("section_title", "")),
                        "search_mode": search_mode,
                        "top_k": top_k,
                    },
                }
            )

        logger.info("Retrieved %s chunks using %s", len(documents), search_mode)
        return json.dumps({"documents": documents, "search_mode": search_mode}, ensure_ascii=False)

    return retrieve_papers
