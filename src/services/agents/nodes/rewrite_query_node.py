import logging
import time
from typing import Dict, List

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from ..context import Context
from ..prompts import REWRITE_PROMPT
from ..state import AgentState

logger = logging.getLogger(__name__)


class QueryRewriteOutput(BaseModel):
    """Structured output for query rewriting."""

    rewritten_query: str = Field(
        min_length=1,
        max_length=1000,
        description="The improved query optimized for document retrieval",
    )
    reasoning: str = Field(
        max_length=1000,
        description="Brief explanation of how the query was improved",
    )


async def ainvoke_rewrite_query_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, str | List]:
    """Rewrite the original query for better document retrieval using the LLM."""
    logger.info("NODE: rewrite_query")
    start_time = time.time()

    original_question = state.get("original_query") or state["messages"][0].content
    current_attempt = state.get("retrieval_attempts", 0)
    logger.debug("Rewriting query of length %s", len(original_question))

    span = None
    if runtime.context.langfuse_enabled and runtime.context.trace:
        try:
            span = runtime.context.langfuse_tracer.create_span(
                trace=runtime.context.trace,
                name="query_rewriting",
                input_data={"original_query": original_question, "attempt": current_attempt},
                metadata={
                    "node": "rewrite_query",
                    "strategy": "llm_based_expansion",
                    "model": runtime.context.model_name,
                },
            )
        except Exception as e:
            logger.warning("Failed to create span for rewrite_query node: %s", e)

    try:
        llm = runtime.context.ollama_client.get_langchain_model(
            model=runtime.context.model_name,
            temperature=0.3,
        )
        structured_llm = llm.with_structured_output(QueryRewriteOutput)
        prompt = REWRITE_PROMPT.format(question=original_question)

        llm_start = time.time()
        result: QueryRewriteOutput = await structured_llm.ainvoke(prompt)
        rewritten_query = result.rewritten_query.strip()
        reasoning = result.reasoning
        llm_duration = time.time() - llm_start

        logger.info(
            "Query rewrite completed in %.2fs (original_length=%s, rewritten_length=%s)",
            llm_duration,
            len(original_question),
            len(rewritten_query),
        )
        logger.debug("Query rewrite rationale: %s", reasoning)

    except Exception as e:
        logger.error("Failed to rewrite query using LLM: %s", e)
        logger.warning("Falling back to bounded keyword expansion")
        suffix = " research paper arxiv machine learning"
        rewritten_query = f"{original_question[: max(1, 1000 - len(suffix))]}{suffix}"
        reasoning = "Fallback keyword expansion due to LLM rewrite failure"

    if span:
        execution_time = (time.time() - start_time) * 1000
        runtime.context.langfuse_tracer.end_span(
            span,
            output={
                "rewritten_query": rewritten_query,
                "reasoning": reasoning,
                "original_query": original_question,
            },
            metadata={
                "execution_time_ms": execution_time,
                "original_length": len(original_question),
                "rewritten_length": len(rewritten_query),
                "llm_duration_seconds": llm_duration if "llm_duration" in locals() else None,
            },
        )

    return {
        "messages": [HumanMessage(content=rewritten_query)],
        "rewritten_query": rewritten_query,
    }
