import logging
import time
from typing import Dict, Literal

from langgraph.runtime import Runtime

from ..context import Context
from ..models import GuardrailScoring
from ..prompts import GUARDRAIL_PROMPT
from ..state import AgentState
from .utils import get_latest_query

logger = logging.getLogger(__name__)


def continue_after_guardrail(state: AgentState, runtime: Runtime[Context]) -> Literal["continue", "out_of_scope"]:
    """Route based on the configured guardrail score threshold."""
    guardrail_result = state.get("guardrail_result")
    if not guardrail_result:
        logger.warning("No guardrail result found, defaulting to continue")
        return "continue"

    score = guardrail_result.score
    threshold = runtime.context.guardrail_threshold
    logger.info("Guardrail score=%s threshold=%s", score, threshold)
    return "continue" if score >= threshold else "out_of_scope"


async def ainvoke_guardrail_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, GuardrailScoring]:
    """Evaluate whether the latest query is in the configured research scope."""
    logger.info("NODE: guardrail_validation")
    start_time = time.time()
    query = get_latest_query(state["messages"])
    logger.debug("Evaluating guardrail query of length %s", len(query))

    span = None
    if runtime.context.langfuse_enabled and runtime.context.trace:
        try:
            span = runtime.context.langfuse_tracer.create_span(
                trace=runtime.context.trace,
                name="guardrail_validation",
                input_data={"query": query, "threshold": runtime.context.guardrail_threshold},
                metadata={"node": "guardrail", "model": runtime.context.model_name},
            )
        except Exception as e:
            logger.warning("Failed to create span for guardrail validation: %s", e)

    try:
        guardrail_prompt = GUARDRAIL_PROMPT.format(question=query)
        llm = runtime.context.ollama_client.get_langchain_model(
            model=runtime.context.model_name,
            temperature=0.0,
        )
        structured_llm = llm.with_structured_output(GuardrailScoring)
        response = await structured_llm.ainvoke(guardrail_prompt)
        logger.info("Guardrail evaluation completed with score=%s", response.score)
        logger.debug("Guardrail rationale: %s", response.reason)

        if span:
            execution_time = (time.time() - start_time) * 1000
            runtime.context.langfuse_tracer.end_span(
                span,
                output={
                    "score": response.score,
                    "reason": response.reason,
                    "decision": "continue" if response.score >= runtime.context.guardrail_threshold else "out_of_scope",
                },
                metadata={"execution_time_ms": execution_time, "threshold": runtime.context.guardrail_threshold},
            )

    except Exception as e:
        logger.error("LLM guardrail validation failed; using conservative fallback: %s", e)
        response = GuardrailScoring(score=50, reason="LLM validation failed; conservative fallback applied")

        if span:
            execution_time = (time.time() - start_time) * 1000
            runtime.context.langfuse_tracer.update_span(
                span,
                output={"score": response.score, "reason": response.reason, "error": type(e).__name__},
                metadata={"execution_time_ms": execution_time, "fallback": True},
                level="WARNING",
            )
            runtime.context.langfuse_tracer.end_span(span)

    return {"guardrail_result": response}
