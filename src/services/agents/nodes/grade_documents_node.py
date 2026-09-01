import logging
import time
from typing import Dict

from langgraph.runtime import Runtime

from ..context import Context
from ..models import GradeDocuments, GradingResult
from ..prompts import GRADE_DOCUMENTS_PROMPT
from ..state import AgentState
from .utils import extract_sources_from_tool_messages, get_latest_context, get_latest_query

logger = logging.getLogger(__name__)


async def ainvoke_grade_documents_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, str | list]:
    """Grade the latest retrieval result and route to generation or query rewriting."""
    logger.info("NODE: grade_documents")
    start_time = time.time()

    question = get_latest_query(state["messages"])
    context = get_latest_context(state["messages"])

    span = None
    if runtime.context.langfuse_enabled and runtime.context.trace:
        try:
            span = runtime.context.langfuse_tracer.create_span(
                trace=runtime.context.trace,
                name="document_grading",
                input_data={
                    "query": question,
                    "context_length": len(context) if context else 0,
                    "has_context": bool(context),
                },
                metadata={
                    "node": "grade_documents",
                    "model": runtime.context.model_name,
                },
            )
        except Exception as exc:
            logger.warning("Failed to create grading span: %s", exc)

    if not context:
        if span:
            runtime.context.langfuse_tracer.end_span(
                span,
                output={"routing_decision": "rewrite_query", "reason": "no_context"},
                metadata={"execution_time_ms": (time.time() - start_time) * 1000},
            )
        return {
            "routing_decision": "rewrite_query",
            "grading_results": [],
            "relevant_sources": [],
            "relevant_tool_artefacts": None,
        }

    try:
        grading_prompt = GRADE_DOCUMENTS_PROMPT.format(context=context, question=question)
        llm = runtime.context.ollama_client.get_langchain_model(
            model=runtime.context.model_name,
            temperature=0.0,
        )
        structured_llm = llm.with_structured_output(GradeDocuments)
        grading_response = await structured_llm.ainvoke(grading_prompt)

        is_relevant = grading_response.binary_score == "yes"
        score = 1.0 if is_relevant else 0.0
        grading_result = GradingResult(
            document_id="retrieved_docs",
            is_relevant=is_relevant,
            score=score,
            reasoning=grading_response.reasoning,
        )
    except Exception as exc:
        logger.error("LLM grading failed: %s; using context-length fallback", exc)
        is_relevant = len(context.strip()) > 50
        score = 1.0 if is_relevant else 0.0
        grading_result = GradingResult(
            document_id="retrieved_docs",
            is_relevant=is_relevant,
            score=score,
            reasoning=(
                "Fallback heuristic (LLM failed): sufficient content"
                if is_relevant
                else "Fallback heuristic (LLM failed): insufficient content"
            ),
        )

    route = "generate_answer" if is_relevant else "rewrite_query"
    relevant_sources = extract_sources_from_tool_messages(state["messages"]) if is_relevant else []

    if span:
        runtime.context.langfuse_tracer.end_span(
            span,
            output={
                "routing_decision": route,
                "is_relevant": is_relevant,
                "score": score,
                "reasoning": grading_result.reasoning,
                "source_count": len(relevant_sources),
            },
            metadata={
                "execution_time_ms": (time.time() - start_time) * 1000,
                "context_length": len(context),
            },
        )

    return {
        "routing_decision": route,
        "grading_results": [grading_result],
        "relevant_sources": relevant_sources,
    }
