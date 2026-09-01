import logging
from typing import List

import httpx
from src.schemas.embeddings.jina import JinaEmbeddingRequest, JinaEmbeddingResponse

logger = logging.getLogger(__name__)


class JinaEmbeddingsClient:
    """Client for Jina AI embeddings API using retrieval-oriented embeddings."""

    def __init__(self, api_key: str, base_url: str = "https://api.jina.ai/v1", dimensions: int = 1024):
        """Initialize Jina embeddings client.

        :param api_key: Jina API key
        :param base_url: API base URL
        :param dimensions: Embedding dimension requested from Jina and used by OpenSearch
        """
        self.api_key = api_key
        self.base_url = base_url
        self.dimensions = dimensions
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("Jina embeddings client initialized (dimensions=%s)", dimensions)

    async def embed_passages(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Embed text passages for indexing."""
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            request_data = JinaEmbeddingRequest(
                model="jina-embeddings-v3",
                task="retrieval.passage",
                dimensions=self.dimensions,
                input=batch,
            )

            try:
                response = await self.client.post(
                    f"{self.base_url}/embeddings", headers=self.headers, json=request_data.model_dump()
                )
                response.raise_for_status()

                result = JinaEmbeddingResponse(**response.json())
                batch_embeddings = [item["embedding"] for item in result.data]
                embeddings.extend(batch_embeddings)

                logger.debug(f"Embedded batch of {len(batch)} passages")

            except httpx.HTTPError as e:
                logger.error(f"Error embedding passages: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in embed_passages: {e}")
                raise

        logger.info(f"Successfully embedded {len(texts)} passages")
        return embeddings

    async def embed_query(self, query: str) -> List[float]:
        """Embed a search query."""
        request_data = JinaEmbeddingRequest(
            model="jina-embeddings-v3",
            task="retrieval.query",
            dimensions=self.dimensions,
            input=[query],
        )

        try:
            response = await self.client.post(f"{self.base_url}/embeddings", headers=self.headers, json=request_data.model_dump())
            response.raise_for_status()

            result = JinaEmbeddingResponse(**response.json())
            embedding = result.data[0]["embedding"]

            logger.debug(f"Embedded query: '{query[:50]}...'")
            return embedding

        except httpx.HTTPError as e:
            logger.error(f"Error embedding query: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in embed_query: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
