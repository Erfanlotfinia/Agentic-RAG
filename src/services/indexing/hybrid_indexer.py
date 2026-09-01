import logging
from typing import Dict, List

from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.opensearch.client import OpenSearchClient

from .text_chunker import TextChunker

logger = logging.getLogger(__name__)


class HybridIndexingService:
    """Chunk, embed, and index papers for hybrid retrieval."""

    def __init__(self, chunker: TextChunker, embeddings_client: JinaEmbeddingsClient, opensearch_client: OpenSearchClient):
        self.chunker = chunker
        self.embeddings_client = embeddings_client
        self.opensearch_client = opensearch_client
        logger.info("Hybrid indexing service initialized")

    async def close(self) -> None:
        """Close network clients owned by this indexing service."""
        try:
            await self.embeddings_client.close()
        finally:
            self.opensearch_client.close()

    @staticmethod
    def _document_id(arxiv_id: str, chunk_index: int) -> str:
        """Build a stable OpenSearch document ID for idempotent paper indexing."""
        return f"{arxiv_id}:{chunk_index}"

    async def index_paper(self, paper_data: Dict, replace_existing: bool = False) -> Dict[str, int]:
        """Index one paper without deleting a healthy previous version up front.

        Replacement uses deterministic document IDs. The complete new set is
        indexed first. Obsolete documents are removed only after every new chunk
        has been written successfully, so embedding/indexing failures preserve
        the previously searchable paper.
        """
        arxiv_id = paper_data.get("arxiv_id")
        paper_id = str(paper_data.get("id", ""))

        if not arxiv_id:
            logger.error("Paper missing arxiv_id")
            return {"chunks_created": 0, "chunks_indexed": 0, "embeddings_generated": 0, "errors": 1}

        try:
            chunks = self.chunker.chunk_paper(
                title=paper_data.get("title", ""),
                abstract=paper_data.get("abstract", ""),
                full_text=paper_data.get("raw_text", paper_data.get("full_text", "")),
                arxiv_id=arxiv_id,
                paper_id=paper_id,
                sections=paper_data.get("sections"),
            )

            if not chunks:
                logger.error("No retrievable chunks created for paper %s", arxiv_id)
                return {"chunks_created": 0, "chunks_indexed": 0, "embeddings_generated": 0, "errors": 1}

            logger.info("Created %s chunks for paper %s", len(chunks), arxiv_id)

            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = await self.embeddings_client.embed_passages(texts=chunk_texts, batch_size=50)

            if len(embeddings) != len(chunks):
                logger.error("Embedding count mismatch for %s: %s != %s", arxiv_id, len(embeddings), len(chunks))
                return {
                    "chunks_created": len(chunks),
                    "chunks_indexed": 0,
                    "embeddings_generated": len(embeddings),
                    "errors": 1,
                }

            chunks_with_embeddings = []
            document_ids = []
            for chunk, embedding in zip(chunks, embeddings):
                document_id = self._document_id(arxiv_id, chunk.metadata.chunk_index)
                document_ids.append(document_id)
                chunk_data = {
                    "chunk_id": document_id,
                    "arxiv_id": chunk.arxiv_id,
                    "paper_id": chunk.paper_id,
                    "chunk_index": chunk.metadata.chunk_index,
                    "chunk_text": chunk.text,
                    "chunk_word_count": chunk.metadata.word_count,
                    "start_char": chunk.metadata.start_char,
                    "end_char": chunk.metadata.end_char,
                    "section_title": chunk.metadata.section_title,
                    "embedding_model": "jina-embeddings-v3",
                    "title": paper_data.get("title", ""),
                    "authors": ", ".join(paper_data.get("authors", []))
                    if isinstance(paper_data.get("authors"), list)
                    else paper_data.get("authors", ""),
                    "abstract": paper_data.get("abstract", ""),
                    "categories": paper_data.get("categories", []),
                    "published_date": paper_data.get("published_date"),
                }
                chunks_with_embeddings.append(
                    {"document_id": document_id, "chunk_data": chunk_data, "embedding": embedding}
                )

            results = self.opensearch_client.bulk_index_chunks(chunks_with_embeddings)
            failed = results["failed"]
            logger.info(
                "Indexed paper %s: %s chunks successful, %s failed",
                arxiv_id,
                results["success"],
                failed,
            )

            errors = failed
            if results["success"] != len(chunks):
                errors = max(errors, 1)

            if errors == 0 and replace_existing:
                self.opensearch_client.delete_stale_paper_chunks(arxiv_id, document_ids)

            return {
                "chunks_created": len(chunks),
                "chunks_indexed": results["success"],
                "embeddings_generated": len(embeddings),
                "errors": errors,
            }

        except Exception:
            logger.exception("Error indexing paper %s", arxiv_id)
            return {"chunks_created": 0, "chunks_indexed": 0, "embeddings_generated": 0, "errors": 1}

    async def index_papers_batch(self, papers: List[Dict], replace_existing: bool = False) -> Dict[str, int]:
        """Index multiple papers and aggregate per-paper error counts."""
        total_stats = {
            "papers_processed": 0,
            "papers_failed": 0,
            "total_chunks_created": 0,
            "total_chunks_indexed": 0,
            "total_embeddings_generated": 0,
            "total_errors": 0,
        }

        for paper in papers:
            stats = await self.index_paper(paper, replace_existing=replace_existing)

            total_stats["papers_processed"] += 1
            total_stats["total_chunks_created"] += stats["chunks_created"]
            total_stats["total_chunks_indexed"] += stats["chunks_indexed"]
            total_stats["total_embeddings_generated"] += stats["embeddings_generated"]
            total_stats["total_errors"] += stats["errors"]
            if stats["errors"] > 0:
                total_stats["papers_failed"] += 1

        logger.info(
            "Batch indexing complete: %s papers processed, %s failed, %s chunks indexed",
            total_stats["papers_processed"],
            total_stats["papers_failed"],
            total_stats["total_chunks_indexed"],
        )
        return total_stats

    async def reindex_paper(self, arxiv_id: str, paper_data: Dict) -> Dict[str, int]:
        """Safely replace a paper's retrieval documents after the new set succeeds."""
        if paper_data.get("arxiv_id") and paper_data["arxiv_id"] != arxiv_id:
            raise ValueError("paper_data arxiv_id does not match the requested paper")
        paper_data = {**paper_data, "arxiv_id": arxiv_id}
        return await self.index_paper(paper_data, replace_existing=True)
