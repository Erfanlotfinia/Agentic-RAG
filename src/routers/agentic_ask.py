import logging

from fastapi import APIRouter, HTTPException

from src.dependencies import AgenticRAGDep, LangfuseDep
from src.schemas.api.ask import AgenticAskResponse, AskRequest, FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["agentic-rag"])


@router.post("/ask-agentic", response_model=AgenticAskResponse)
async def ask_agentic(
    request: AskRequest,
    agentic_rag: AgenticRAGDep,
) -> AgenticAskResponse:
    """Run adaptive Agentic RAG using the request's actual retrieval settings."""
    try:
        result = await agentic_rag.ask(
            query=request.query,
            model=request.model,
            top_k=request.top_k,
            use_hybrid=request.use_hybrid,
            categories=request.categories,
            session_id=request.session_id,
        )

        return AgenticAskResponse(
            query=result["query"],
            answer=result["answer"],
            sources=result.get("sources", []),
            chunks_used=result.get("chunks_used", 0),
            search_mode=result.get("search_mode", "hybrid" if request.use_hybrid else "bm25"),
            reasoning_steps=result.get("reasoning_steps", []),
            retrieval_attempts=result.get("retrieval_attempts", 0),
            rewritten_query=result.get("rewritten_query"),
            session_id=request.session_id,
            trace_id=result.get("trace_id"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Agentic RAG request failed")
        raise HTTPException(status_code=500, detail="Unable to process the Agentic RAG request")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    langfuse_tracer: LangfuseDep,
) -> FeedbackResponse:
    """Submit user feedback for an Agentic RAG trace."""
    try:
        if not langfuse_tracer or not langfuse_tracer.client:
            raise HTTPException(status_code=503, detail="Langfuse tracing is disabled. Cannot submit feedback.")

        success = langfuse_tracer.submit_feedback(
            trace_id=request.trace_id,
            score=request.score,
            comment=request.comment,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to submit feedback to Langfuse")

        langfuse_tracer.flush()
        return FeedbackResponse(success=True, message="Feedback recorded successfully")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Feedback submission failed")
        raise HTTPException(status_code=500, detail="Unable to submit feedback")
