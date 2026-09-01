"""Unified OpenSearch client supporting both simple BM25 and hybrid search."""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from opensearchpy import OpenSearch
from src.config import Settings
from src.exceptions import OpenSearchException

from .index_config_hybrid import ARXIV_PAPERS_CHUNKS_MAPPING, HYBRID_RRF_PIPELINE
from .query_builder import QueryBuilder

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """OpenSearch client supporting BM25 and hybrid search with native RRF."""

    def __init__(self, host: str, settings: Settings):
        self.host = host
        self.settings = settings
        self.index_name = f"{settings.opensearch.index_name}-{settings.opensearch.chunk_index_suffix}"

        username = settings.opensearch.username
        password = settings.opensearch.password
        if bool(username) != bool(password):
            raise ValueError("OpenSearch username and password must be configured together")

        use_ssl = settings.opensearch.use_ssl or host.lower().startswith("https://")
        client_options = {
            "hosts": [host],
            "use_ssl": use_ssl,
            "verify_certs": settings.opensearch.verify_certs if use_ssl else False,
            "ssl_show_warn": False,
        }
        if username and password:
            client_options["http_auth"] = (username, password)
        if settings.opensearch.ca_certs:
            client_options["ca_certs"] = settings.opensearch.ca_certs

        self.client = OpenSearch(**client_options)

        logger.info(
            "OpenSearch client initialized with host=%s ssl=%s certificate_verification=%s authentication=%s",
            host,
            use_ssl,
            client_options["verify_certs"],
            bool(username),
        )

    def close(self) -> None:
        """Close the underlying OpenSearch transport."""
        self.client.close()

    def health_check(self) -> bool:
        """Check if OpenSearch cluster is healthy."""
        try:
            health = self.client.cluster.health()
            return health["status"] in ["green", "yellow"]
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics for the hybrid index."""
        try:
            if not self.client.indices.exists(index=self.index_name):
                return {"index_name": self.index_name, "exists": False, "document_count": 0}

            stats_response = self.client.indices.stats(index=self.index_name)
            index_stats = stats_response["indices"][self.index_name]["total"]

            return {
                "index_name": self.index_name,
                "exists": True,
                "document_count": index_stats["docs"]["count"],
                "deleted_count": index_stats["docs"]["deleted"],
                "size_in_bytes": index_stats["store"]["size_in_bytes"],
            }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"index_name": self.index_name, "exists": False, "document_count": 0, "error": str(e)}

    def setup_indices(self, force: bool = False) -> Dict[str, bool]:
        """Setup the hybrid search index and RRF pipeline."""
        results = {}
        results["hybrid_index"] = self._create_hybrid_index(force)
        results["rrf_pipeline"] = self._create_rrf_pipeline(force)
        return results

    def _create_hybrid_index(self, force: bool = False) -> bool:
        """Create the configured hybrid index for BM25/vector/hybrid retrieval."""
        try:
            if force and self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Deleted existing hybrid index: {self.index_name}")

            if not self.client.indices.exists(index=self.index_name):
                mapping = deepcopy(ARXIV_PAPERS_CHUNKS_MAPPING)
                embedding = mapping["mappings"]["properties"]["embedding"]
                embedding["dimension"] = self.settings.opensearch.vector_dimension
                embedding["method"]["space_type"] = self.settings.opensearch.vector_space_type

                self.client.indices.create(index=self.index_name, body=mapping)
                logger.info(
                    "Created hybrid index %s (dimension=%s, space=%s)",
                    self.index_name,
                    self.settings.opensearch.vector_dimension,
                    self.settings.opensearch.vector_space_type,
                )
                return True

            logger.info(f"Hybrid index already exists: {self.index_name}")
            return False

        except Exception as e:
            if "resource_already_exists_exception" in str(e):
                logger.info(f"Hybrid index already exists (created by another worker): {self.index_name}")
                return False
            logger.error(f"Error creating hybrid index: {e}")
            raise

    def _create_rrf_pipeline(self, force: bool = False) -> bool:
        """Create the configured OpenSearch search pipeline used for native RRF."""
        pipeline_id = self.settings.opensearch.rrf_pipeline_name
        pipeline_path = f"/_search/pipeline/{pipeline_id}"

        try:
            exists = False
            try:
                self.client.transport.perform_request("GET", pipeline_path)
                exists = True
            except Exception:
                exists = False

            if exists and not force:
                logger.info(f"RRF search pipeline already exists: {pipeline_id}")
                return False

            if exists and force:
                self.client.transport.perform_request("DELETE", pipeline_path)
                logger.info(f"Deleted existing RRF search pipeline: {pipeline_id}")

            pipeline_body = {
                "description": HYBRID_RRF_PIPELINE["description"],
                "phase_results_processors": HYBRID_RRF_PIPELINE["phase_results_processors"],
            }
            self.client.transport.perform_request("PUT", pipeline_path, body=pipeline_body)
            logger.info(f"Created RRF search pipeline: {pipeline_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating RRF search pipeline: {e}")
            raise

    def search_papers(
        self, query: str, size: int = 10, from_: int = 0, categories: Optional[List[str]] = None, latest: bool = True
    ) -> Dict[str, Any]:
        """BM25 search for papers."""
        return self._search_bm25_only(query=query, size=size, from_=from_, categories=categories, latest=latest)

    def search_chunks_vector(
        self, query_embedding: List[float], size: int = 10, categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Pure vector search on chunks."""
        try:
            filter_clause = []
            if categories:
                filter_clause.append({"terms": {"categories": categories}})

            search_body = {
                "size": size,
                "query": {"knn": {"embedding": {"vector": query_embedding, "k": size}}},
                "_source": {"excludes": ["embedding"]},
            }

            if filter_clause:
                search_body["query"] = {"bool": {"must": [search_body["query"]], "filter": filter_clause}}

            response = self.client.search(index=self.index_name, body=search_body)

            results = {"total": response["hits"]["total"]["value"], "hits": []}

            for hit in response["hits"]["hits"]:
                chunk = hit["_source"]
                chunk["score"] = hit["_score"]
                chunk["chunk_id"] = hit["_id"]
                results["hits"].append(chunk)

            return results

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return {"total": 0, "hits": []}

    def search_unified(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        size: int = 10,
        from_: int = 0,
        categories: Optional[List[str]] = None,
        latest: bool = False,
        use_hybrid: bool = True,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Unified search method supporting BM25 and native hybrid modes.

        ``latest=True`` explicitly selects date-sorted BM25 because relevance
        fusion and newest-first sorting are different ordering contracts.
        """
        try:
            if latest or not query_embedding or not use_hybrid:
                return self._search_bm25_only(
                    query=query,
                    size=size,
                    from_=from_,
                    categories=categories,
                    latest=latest,
                    min_score=min_score,
                )

            return self._search_hybrid_native(
                query=query,
                query_embedding=query_embedding,
                size=size,
                from_=from_,
                categories=categories,
                min_score=min_score,
            )

        except Exception as exc:
            logger.exception("Unified OpenSearch request failed")
            raise OpenSearchException("Search backend request failed") from exc

    def _search_bm25_only(
        self,
        query: str,
        size: int,
        from_: int,
        categories: Optional[List[str]],
        latest: bool,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Pure BM25 search implementation."""
        builder = QueryBuilder(
            query=query,
            size=size,
            from_=from_,
            categories=categories,
            latest_papers=latest,
            search_chunks=True,
        )
        search_body = builder.build()
        if min_score > 0:
            search_body["min_score"] = min_score

        response = self.client.search(index=self.index_name, body=search_body)

        results = {"total": response["hits"]["total"]["value"], "hits": []}

        for hit in response["hits"]["hits"]:
            chunk = hit["_source"]
            chunk["score"] = hit["_score"]
            chunk["chunk_id"] = hit["_id"]

            if "highlight" in hit:
                chunk["highlights"] = hit["highlight"]

            results["hits"].append(chunk)

        logger.info(f"BM25 search for '{query[:50]}...' returned {results['total']} results")
        return results

    def _search_hybrid_native(
        self,
        query: str,
        query_embedding: List[float],
        size: int,
        from_: int,
        categories: Optional[List[str]],
        min_score: float,
    ) -> Dict[str, Any]:
        """Native OpenSearch 2.19 hybrid search with RRF, filtering, and pagination."""
        multiplier = max(1, self.settings.opensearch.hybrid_search_size_multiplier)
        pagination_depth = min(max((from_ + size) * multiplier, size * multiplier), 10000)
        builder = QueryBuilder(
            query=query,
            size=pagination_depth,
            from_=0,
            categories=categories,
            latest_papers=False,
            search_chunks=True,
        )
        bm25_search_body = builder.build()
        bm25_query = bm25_search_body["query"]

        hybrid_body = {
            "pagination_depth": pagination_depth,
            "queries": [
                bm25_query,
                {"knn": {"embedding": {"vector": query_embedding, "k": pagination_depth}}},
            ],
        }
        if categories:
            hybrid_body["filter"] = {"terms": {"categories": categories}}

        search_body = {
            "from": from_,
            "size": size,
            "query": {"hybrid": hybrid_body},
            "_source": bm25_search_body["_source"],
            "highlight": bm25_search_body["highlight"],
        }
        if min_score > 0:
            search_body["min_score"] = min_score

        response = self.client.search(
            index=self.index_name,
            body=search_body,
            params={"search_pipeline": self.settings.opensearch.rrf_pipeline_name},
        )

        results = {"total": response["hits"]["total"]["value"], "hits": []}

        for hit in response["hits"]["hits"]:
            chunk = hit["_source"]
            chunk["score"] = hit["_score"]
            chunk["chunk_id"] = hit["_id"]

            if "highlight" in hit:
                chunk["highlights"] = hit["highlight"]

            results["hits"].append(chunk)

        logger.info(
            "Native hybrid search for %r returned %s hits (%s total matches)",
            query[:50],
            len(results["hits"]),
            results["total"],
        )
        return results

    def search_chunks_hybrid(
        self,
        query: str,
        query_embedding: List[float],
        size: int = 10,
        categories: Optional[List[str]] = None,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Hybrid search combining BM25 and vector similarity using native RRF."""
        return self._search_hybrid_native(
            query=query,
            query_embedding=query_embedding,
            size=size,
            from_=0,
            categories=categories,
            min_score=min_score,
        )

    def index_chunk(self, chunk_data: Dict[str, Any], embedding: List[float]) -> bool:
        """Index a single chunk with its embedding."""
        try:
            chunk_data["embedding"] = embedding
            response = self.client.index(index=self.index_name, body=chunk_data, refresh=True)
            return response["result"] in ["created", "updated"]

        except Exception as e:
            logger.error(f"Error indexing chunk: {e}")
            return False

    def bulk_index_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Bulk index multiple chunks with embeddings."""
        from opensearchpy import helpers

        try:
            actions = []
            for chunk in chunks:
                chunk_data = chunk["chunk_data"].copy()
                chunk_data["embedding"] = chunk["embedding"]
                actions.append({"_index": self.index_name, "_source": chunk_data})

            success, failed = helpers.bulk(self.client, actions, refresh=True)
            logger.info(f"Bulk indexed {success} chunks, {len(failed)} failed")
            return {"success": success, "failed": len(failed)}

        except Exception as e:
            logger.error(f"Bulk chunk indexing error: {e}")
            raise

    def delete_paper_chunks(self, arxiv_id: str) -> bool:
        """Delete all chunks for a specific paper."""
        try:
            response = self.client.delete_by_query(
                index=self.index_name, body={"query": {"term": {"arxiv_id": arxiv_id}}}, refresh=True
            )
            deleted = response.get("deleted", 0)
            logger.info(f"Deleted {deleted} chunks for paper {arxiv_id}")
            return deleted > 0

        except Exception as e:
            logger.error(f"Error deleting chunks: {e}")
            return False

    def get_chunks_by_paper(self, arxiv_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific paper sorted by chunk index."""
        try:
            search_body = {
                "query": {"term": {"arxiv_id": arxiv_id}},
                "size": 1000,
                "sort": [{"chunk_index": "asc"}],
                "_source": {"excludes": ["embedding"]},
            }

            response = self.client.search(index=self.index_name, body=search_body)

            chunks = []
            for hit in response["hits"]["hits"]:
                chunk = hit["_source"]
                chunk["chunk_id"] = hit["_id"]
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Error getting chunks: {e}")
            return []
