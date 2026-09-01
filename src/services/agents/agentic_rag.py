import logging
import time
import uuid
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.services.cache.client import CacheClient
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient

from .config import GraphConfig
from .context import Context
from .nodes import (
    ainvoke_generate_answer_step,
    ainvoke_grade_documents_step,
    ainvoke_guardrail_step,
    ainvoke_out_of_scope_step,
    ainvoke_retrieve_step,
    ainvoke_rewrite_query_step,
    continue_after_guardrail,
)
from .nodes.utils import get_latest_retrieved_documents
from .state import AgentState
from .tools import create_retriever_tool

logger = logging.getLogger(__name__)


class AgenticRAGService:
    """Adaptive single-agent RAG workflow backed by shared retrieval services."""

    def __init__(
        self,
        opensearch_client: OpenSearchClient,
        ollama_client: OllamaClient,
        embeddings_client: JinaEmbeddingsClient,
        langfuse_tracer: Optional[LangfuseTracer] = None,
        cache_client: Optional[CacheClient] = None,
        graph_config: Optional[GraphConfig] = None,
    ):
        self.opensearch = opensearch_client
        self.ollama = ollama_client
        self.embeddings = embeddings_client
        self.langfuse_tracer = langfuse_tracer
        self.cache_client = cache_client
        self.graph_config = graph_config or GraphConfig()

        self.graph = self._build_graph(
            top_k=self.graph_config.top_k,
            use_hybrid=self.graph_config.use_hybrid,
            categories=None,
        )
        logger.info("AgenticRAGService initialized")

    def _build_graph(
        self,
        top_k: Optional[int] = None,
        use_hybrid: Optional[bool] = None,
        categories: Optional[List[str]] = None,
    ):
        """Build and compile a graph for the requested retrieval configuration."""
        resolved_top_k = top_k if top_k is not None else self.graph_config.top_k
        resolved_hybrid = use_hybrid if use_hybrid is not None else self.graph_config.use_hybrid

        workflow = StateGraph(AgentState, context_schema=Context)
        retriever_tool = create_retriever_tool(
            opensearch_client=self.opensearch,
            embeddings_client=self.embeddings,
            top_k=resolved_top_k,
            use_hybrid=resolved_hybrid,
            categories=categories,
        )

        workflow.add_node("guardrail", ainvoke_guardrail_step)
        workflow.add_node("out_of_scope", ainvoke_out_of_scope_step)
        workflow.add_node("retrieve", ainvoke_retrieve_step)
        workflow.add_node("tool_retrieve", ToolNode([retriever_tool]))
        workflow.add_node("grade_documents", ainvoke_grade_documents_step)
        workflow.add_node("rewrite_query", ainvoke_rewrite_query_step)
        workflow.add_node("generate_answer", ainvoke_generate_answer_step)

        workflow.add_edge(START, "guardrail")
        workflow.add_conditional_edges(
            "guardrail",
            continue_after_guardrail,
            {"continue": "retrieve", "out_of_scope": "out_of_scope"},
        )
        workflow.add_edge("out_of_scope", END)
        workflow.add_conditional_edges(
            "retrieve",
            tools_condition,
            {"tools": "tool_retrieve", END: END},
        )
        workflow.add_edge("tool_retrieve", "grade_documents")
        workflow.add_conditional_edges(
            "grade_documents",
            lambda state: state.get("routing_decision", "generate_answer"),
            {"generate_answer": "generate_answer", "rewrite_query": "rewrite_query"},
        )
        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("generate_answer", END)

        return workflow.compile()

    async def ask(
        self,
        query: str,
        user_id: str = "api_user",
        model: Optional[str] = None,
        top_k: Optional[int] = None,
        use_hybrid: Optional[bool] = None,
        categories: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> dict:
        """Run Agentic RAG with request-scoped retrieval options.

        When a caller supplies ``session_id``, user/assistant turns are loaded
        from and stored in Redis. This keeps conversation history consistent
        across the multiple Uvicorn workers used by the Docker image.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        model_to_use = model or self.graph_config.model
        resolved_top_k = top_k if top_k is not None else self.graph_config.top_k
        resolved_hybrid = use_hybrid if use_hybrid is not None else self.graph_config.use_hybrid
        persist_session = bool(session_id)
        resolved_session_id = session_id or f"request-{uuid.uuid4().hex}"

        if resolved_top_k == self.graph_config.top_k and resolved_hybrid == self.graph_config.use_hybrid and not categories:
            graph = self.graph
        else:
            graph = self._build_graph(
                top_k=resolved_top_k,
                use_hybrid=resolved_hybrid,
                categories=categories,
            )

        metadata = {
            "env": self.graph_config.settings.environment,
            "service": "agentic_rag",
            "top_k": resolved_top_k,
            "use_hybrid": resolved_hybrid,
            "categories": categories or [],
            "model": model_to_use,
            "session_id": resolved_session_id,
        }

        trace = None
        if self.langfuse_tracer and self.langfuse_tracer.client:
            trace = self.langfuse_tracer.client.start_as_current_span(name="agentic_rag_request")

        async def _execute_with_trace():
            if trace is not None:
                with trace as trace_obj:
                    trace_obj.update(
                        input={"query": query},
                        metadata=metadata,
                        user_id=user_id,
                        session_id=resolved_session_id,
                    )
                    return await self._run_workflow(
                        graph=graph,
                        query=query,
                        model_to_use=model_to_use,
                        user_id=user_id,
                        session_id=resolved_session_id,
                        persist_session=persist_session,
                        top_k=resolved_top_k,
                        use_hybrid=resolved_hybrid,
                        categories=categories,
                        trace=trace_obj,
                    )

            return await self._run_workflow(
                graph=graph,
                query=query,
                model_to_use=model_to_use,
                user_id=user_id,
                session_id=resolved_session_id,
                persist_session=persist_session,
                top_k=resolved_top_k,
                use_hybrid=resolved_hybrid,
                categories=categories,
                trace=None,
            )

        try:
            return await _execute_with_trace()
        except Exception as exc:
            logger.error("Agentic RAG execution failed: %s", exc, exc_info=True)
            raise

    async def _load_history(self, session_id: str, persist_session: bool) -> List:
        if not persist_session or not self.cache_client:
            return []

        history = await self.cache_client.get_conversation_history(session_id)
        messages = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages

    async def _run_workflow(
        self,
        graph,
        query: str,
        model_to_use: str,
        user_id: str,
        session_id: str,
        persist_session: bool,
        top_k: int,
        use_hybrid: bool,
        categories: Optional[List[str]],
        trace,
    ) -> dict:
        start_time = time.time()
        history_messages = await self._load_history(session_id, persist_session)

        state_input = {
            "messages": [*history_messages, HumanMessage(content=query)],
            "retrieval_attempts": 0,
            "guardrail_result": None,
            "routing_decision": None,
            "sources": None,
            "relevant_sources": [],
            "relevant_tool_artefacts": None,
            "grading_results": [],
            "metadata": {},
            "original_query": None,
            "rewritten_query": None,
        }

        runtime_context = Context(
            ollama_client=self.ollama,
            opensearch_client=self.opensearch,
            embeddings_client=self.embeddings,
            langfuse_tracer=self.langfuse_tracer,
            trace=trace,
            langfuse_enabled=bool(self.langfuse_tracer and self.langfuse_tracer.client),
            model_name=model_to_use,
            temperature=self.graph_config.temperature,
            top_k=top_k,
            use_hybrid=use_hybrid,
            categories=categories,
            max_retrieval_attempts=self.graph_config.max_retrieval_attempts,
            guardrail_threshold=self.graph_config.guardrail_threshold,
        )

        config = {"configurable": {"thread_id": session_id}}
        if self.langfuse_tracer and trace:
            try:
                config["callbacks"] = [CallbackHandler()]
            except Exception as exc:
                logger.warning("Failed to create Langfuse CallbackHandler: %s", exc)

        try:
            result = await graph.ainvoke(state_input, config=config, context=runtime_context)
            execution_time = time.time() - start_time

            answer = self._extract_answer(result)
            sources = self._extract_sources(result)
            retrieval_attempts = result.get("retrieval_attempts", 0)
            reasoning_steps = self._extract_reasoning_steps(result)
            latest_documents = get_latest_retrieved_documents(result.get("messages", []))
            chunks_used = len(latest_documents) if sources else 0
            trace_id = self.langfuse_tracer.get_trace_id(trace) if self.langfuse_tracer and trace else None

            if persist_session and self.cache_client:
                await self.cache_client.store_conversation_turn(
                    session_id=session_id,
                    user_message=query,
                    assistant_message=answer,
                )

            if trace:
                trace.update(
                    output={
                        "answer": answer,
                        "sources_count": len(sources),
                        "chunks_used": chunks_used,
                        "retrieval_attempts": retrieval_attempts,
                        "reasoning_steps": reasoning_steps,
                        "execution_time": execution_time,
                    }
                )
                self.langfuse_tracer.flush()

            return {
                "query": query,
                "answer": answer,
                "sources": sources,
                "chunks_used": chunks_used,
                "search_mode": "hybrid" if use_hybrid else "bm25",
                "reasoning_steps": reasoning_steps,
                "retrieval_attempts": retrieval_attempts,
                "rewritten_query": result.get("rewritten_query"),
                "execution_time": execution_time,
                "guardrail_score": result.get("guardrail_result").score if result.get("guardrail_result") else None,
                "trace_id": trace_id,
                "session_id": session_id,
            }
        except Exception as exc:
            if trace:
                trace.update(output={"error": str(exc)}, level="ERROR")
                self.langfuse_tracer.flush()
            raise

    def _extract_answer(self, result: dict) -> str:
        messages = result.get("messages", [])
        if not messages:
            return "No answer generated."
        final_message = messages[-1]
        return final_message.content if hasattr(final_message, "content") else str(final_message)

    def _extract_sources(self, result: dict) -> List[str]:
        """Return the public PDF URLs expected by the API schema."""
        urls: List[str] = []
        for source in result.get("relevant_sources", []):
            if hasattr(source, "url"):
                url = source.url
            elif isinstance(source, dict):
                url = source.get("url", "")
            else:
                url = ""
            if url and url not in urls:
                urls.append(url)
        return urls

    def _extract_reasoning_steps(self, result: dict) -> List[str]:
        steps = []
        retrieval_attempts = result.get("retrieval_attempts", 0)
        guardrail_result = result.get("guardrail_result")
        grading_results = result.get("grading_results", [])

        if guardrail_result:
            steps.append(f"Validated query scope (score: {guardrail_result.score}/100)")
            if guardrail_result.score < self.graph_config.guardrail_threshold and retrieval_attempts == 0:
                steps.append("Returned out-of-scope response")
                return steps

        if retrieval_attempts > 0:
            steps.append(f"Retrieved documents ({retrieval_attempts} attempt(s))")

        if grading_results:
            relevant_count = sum(1 for grade in grading_results if grade.is_relevant)
            steps.append(f"Graded documents ({relevant_count} relevant)")

        if result.get("rewritten_query"):
            steps.append("Rewritten query for better results")

        if result.get("relevant_sources"):
            steps.append("Generated answer from context")
        elif retrieval_attempts >= self.graph_config.max_retrieval_attempts:
            steps.append("Stopped after maximum retrieval attempts")

        return steps

    def get_graph_visualization(self) -> bytes:
        """Get the default workflow visualization as PNG."""
        try:
            return self.graph.get_graph().draw_mermaid_png()
        except ImportError as exc:
            raise ImportError(
                "Graph visualization requires graph visualization dependencies. "
                "Install the optional visualization dependencies first."
            ) from exc

    def get_graph_mermaid(self) -> str:
        """Get the default workflow as Mermaid syntax."""
        return self.graph.get_graph().draw_mermaid()

    def get_graph_ascii(self) -> str:
        """Get the default workflow as ASCII output."""
        return self.graph.get_graph().print_ascii()
