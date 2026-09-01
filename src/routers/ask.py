import json
import logging
import time
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.dependencies import CacheDep, EmbeddingsDep, LangfuseDep, OllamaDep, OpenSearchDep
from src.schemas.api.ask import AskRequest, AskResponse
from src.services.langfuse.tracer import RAGTracer

logger = logging.getLogger(__name__)

ask_router = APIRouter(tags=["ask"])
stream_router = APIRouter(tags=["stream"])


def _cache_matches_requested_mode(request: AskRequest, response: AskResponse) -> bool:
    """Return True only when a cached response satisfies the requested retrieval mode."""
    requested_mode = "hybrid" if request.use_hybrid else "bm25"
    return response.search_mode == requested_mode


async def _prepare_chunks_and_sources(
    request: AskRequest,
    opensearch_client,
    embeddings_service,
    rag_tracer: RAGTracer,
    trace=None,
) -> tuple[List[Dict], List[str], List[str], str]:
    """Retrieve chunks and return the retrieval mode that was actually used."""
    query_embedding = None
    if request.use_hybrid:
        with rag_tracer.trace_embedding(trace, request.query) as embedding_span:
            try:
                query_embedding = await embeddings_service.embed_query(request.query)
                logger.info("Generated query embedding for hybrid search")
            except Exception as exc:
                logger.warning("Failed to generate embeddings, falling back to BM25: %s", exc)
                if embedding_span:
                    rag_tracer.tracer.update_span(embedding_span, output={"success": False, "error": str(exc)})

    effective_search_mode = "hybrid" if request.use_hybrid and query_embedding is not None else "bm25"

    with rag_tracer.trace_search(trace, request.query, request.top_k) as search_span:
        search_results = opensearch_client.search_unified(
            query=request.query,
            query_embedding=query_embedding,
            size=request.top_k,
            from_=0,
            categories=request.categories,
            use_hybrid=effective_search_mode == "hybrid",
            min_score=0.0,
        )

        chunks = []
        arxiv_ids = []
        sources_set = set()

        for hit in search_results.get("hits", []):
            arxiv_id = hit.get("arxiv_id", "")
            chunks.append(
                {
                    "arxiv_id": arxiv_id,
                    "chunk_text": hit.get("chunk_text", hit.get("abstract", "")),
                }
            )

            if arxiv_id:
                arxiv_ids.append(arxiv_id)
                arxiv_id_clean = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
                sources_set.add(f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf")

        rag_tracer.end_search(search_span, chunks, arxiv_ids, search_results.get("total", 0))

    return chunks, sorted(sources_set), arxiv_ids, effective_search_mode


@ask_router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    opensearch_client: OpenSearchDep,
    embeddings_service: EmbeddingsDep,
    ollama_client: OllamaDep,
    langfuse_tracer: LangfuseDep,
    cache_client: CacheDep,
) -> AskResponse:
    """Answer a grounded RAG request with exact-match caching when semantics match."""
    rag_tracer = RAGTracer(langfuse_tracer)
    start_time = time.time()

    with rag_tracer.trace_request("api_user", request.query) as trace:
        try:
            if cache_client:
                try:
                    cached_response = await cache_client.find_cached_response(request)
                    if cached_response and _cache_matches_requested_mode(request, cached_response):
                        logger.info("Returning cached response for exact query and retrieval-mode match")
                        return cached_response
                    if cached_response:
                        logger.info(
                            "Ignoring cached %s response because the request requires %s retrieval",
                            cached_response.search_mode,
                            "hybrid" if request.use_hybrid else "bm25",
                        )
                except Exception as exc:
                    logger.warning("Cache check failed, proceeding with normal flow: %s", exc)

            chunks, sources, _, search_mode = await _prepare_chunks_and_sources(
                request, opensearch_client, embeddings_service, rag_tracer, trace
            )

            if not chunks:
                response = AskResponse(
                    query=request.query,
                    answer="I couldn't find any relevant information in the papers to answer your question.",
                    sources=[],
                    chunks_used=0,
                    search_mode=search_mode,
                )
                rag_tracer.end_request(trace, response.answer, time.time() - start_time)
                return response

            with rag_tracer.trace_prompt_construction(trace, chunks) as prompt_span:
                from src.services.ollama.prompts import RAGPromptBuilder

                prompt_builder = RAGPromptBuilder()
                try:
                    prompt_data = prompt_builder.create_structured_prompt(request.query, chunks)
                    final_prompt = prompt_data["prompt"]
                except Exception:
                    final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)

                rag_tracer.end_prompt(prompt_span, final_prompt)

            with rag_tracer.trace_generation(trace, request.model, final_prompt) as gen_span:
                rag_response = await ollama_client.generate_rag_answer(query=request.query, chunks=chunks, model=request.model)
                answer = rag_response.get("answer", "Unable to generate answer")
                rag_tracer.end_generation(gen_span, answer, request.model)

            response = AskResponse(
                query=request.query,
                answer=answer,
                sources=sources,
                chunks_used=len(chunks),
                search_mode=search_mode,
            )

            rag_tracer.end_request(trace, answer, time.time() - start_time)

            if cache_client and _cache_matches_requested_mode(request, response):
                try:
                    await cache_client.store_response(request, response)
                except Exception as exc:
                    logger.warning("Failed to store response in cache: %s", exc)

            return response

        except HTTPException:
            raise
        except Exception:
            logger.exception("Error processing RAG request")
            raise HTTPException(status_code=500, detail="Unable to process the request")


@stream_router.post("/stream")
async def ask_question_stream(
    request: AskRequest,
    opensearch_client: OpenSearchDep,
    embeddings_service: EmbeddingsDep,
    ollama_client: OllamaDep,
    langfuse_tracer: LangfuseDep,
    cache_client: CacheDep,
) -> StreamingResponse:
    """Stream a grounded RAG response as server-sent data events."""

    async def generate_stream():
        rag_tracer = RAGTracer(langfuse_tracer)
        start_time = time.time()

        with rag_tracer.trace_request("api_user", request.query) as trace:
            try:
                if cache_client:
                    try:
                        cached_response = await cache_client.find_cached_response(request)
                        if cached_response and _cache_matches_requested_mode(request, cached_response):
                            logger.info("Returning cached response for exact streaming query and retrieval-mode match")

                            metadata_response = {
                                "sources": cached_response.sources,
                                "chunks_used": cached_response.chunks_used,
                                "search_mode": cached_response.search_mode,
                            }
                            yield f"data: {json.dumps(metadata_response)}\n\n"

                            for chunk in cached_response.answer.split():
                                yield f"data: {json.dumps({'chunk': chunk + ' '})}\n\n"

                            yield f"data: {json.dumps({'answer': cached_response.answer, 'done': True})}\n\n"
                            return
                        if cached_response:
                            logger.info("Ignoring cached degraded retrieval result for streaming request")
                    except Exception as exc:
                        logger.warning("Cache check failed, proceeding with normal flow: %s", exc)

                chunks, sources, _, search_mode = await _prepare_chunks_and_sources(
                    request, opensearch_client, embeddings_service, rag_tracer, trace
                )

                if not chunks:
                    no_results = {
                        "answer": "No relevant information found.",
                        "sources": [],
                        "chunks_used": 0,
                        "search_mode": search_mode,
                        "done": True,
                    }
                    yield f"data: {json.dumps(no_results)}\n\n"
                    return

                metadata_response = {"sources": sources, "chunks_used": len(chunks), "search_mode": search_mode}
                yield f"data: {json.dumps(metadata_response)}\n\n"

                with rag_tracer.trace_prompt_construction(trace, chunks) as prompt_span:
                    from src.services.ollama.prompts import RAGPromptBuilder

                    prompt_builder = RAGPromptBuilder()
                    final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)
                    rag_tracer.end_prompt(prompt_span, final_prompt)

                with rag_tracer.trace_generation(trace, request.model, final_prompt) as gen_span:
                    full_response = ""
                    async for chunk in ollama_client.generate_rag_answer_stream(
                        query=request.query, chunks=chunks, model=request.model
                    ):
                        if chunk.get("response"):
                            text_chunk = chunk["response"]
                            full_response += text_chunk
                            yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

                        if chunk.get("done", False):
                            rag_tracer.end_generation(gen_span, full_response, request.model)
                            yield f"data: {json.dumps({'answer': full_response, 'done': True})}\n\n"
                            break

                rag_tracer.end_request(trace, full_response, time.time() - start_time)

                if cache_client and full_response:
                    response_to_cache = AskResponse(
                        query=request.query,
                        answer=full_response,
                        sources=sources,
                        chunks_used=len(chunks),
                        search_mode=search_mode,
                    )
                    if _cache_matches_requested_mode(request, response_to_cache):
                        try:
                            await cache_client.store_response(request, response_to_cache)
                        except Exception as exc:
                            logger.warning("Failed to store streaming response in cache: %s", exc)

            except Exception:
                logger.exception("Streaming RAG request failed")
                yield f"data: {json.dumps({'error': 'Unable to process the streaming request'})}\n\n"

    return StreamingResponse(
        generate_stream(), media_type="text/plain", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
