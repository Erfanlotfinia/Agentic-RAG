import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

from langfuse import Langfuse

from src.config import Settings

logger = logging.getLogger(__name__)


class LangfuseTracer:
    """Wrapper around the Langfuse 3.x SDK locked by this project."""

    def __init__(self, settings: Settings):
        self.settings = settings.langfuse
        self.client: Optional[Langfuse] = None

        if self.settings.enabled and self.settings.public_key and self.settings.secret_key:
            try:
                self.client = Langfuse(
                    public_key=self.settings.public_key,
                    secret_key=self.settings.secret_key,
                    host=self.settings.host,
                    flush_at=self.settings.flush_at,
                    flush_interval=self.settings.flush_interval,
                    debug=self.settings.debug,
                )
                logger.info("Langfuse v3 tracing initialized (host: %s)", self.settings.host)
            except Exception as exc:
                logger.error("Failed to initialize Langfuse: %s", exc)
                self.client = None
        else:
            logger.info("Langfuse tracing disabled or missing credentials")

    def get_callback_handler(
        self,
        trace_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ):
        if not self.client:
            return None

        try:
            from langfuse.langchain import CallbackHandler

            return CallbackHandler(
                trace_name=trace_name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata,
                tags=tags,
            )
        except Exception as exc:
            logger.error("Error creating CallbackHandler: %s", exc)
            return None

    @contextmanager
    def trace_langgraph_agent(
        self,
        name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ):
        if not self.client:
            yield (None, None)
            return

        handler = self.get_callback_handler(
            trace_name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
        yield (None, handler)

    def get_trace_id(self, trace=None) -> Optional[str]:
        if not self.client:
            return None
        try:
            return self.client.get_current_trace_id()
        except Exception as exc:
            logger.error("Error getting trace ID: %s", exc)
            return None

    def submit_feedback(
        self,
        trace_id: str,
        score: float,
        name: str = "user-feedback",
        comment: Optional[str] = None,
    ) -> bool:
        if not self.client:
            logger.warning("Cannot submit feedback: Langfuse is disabled")
            return False

        try:
            self.client.score(trace_id=trace_id, name=name, value=score, comment=comment)
            return True
        except Exception as exc:
            logger.error("Error submitting feedback: %s", exc)
            return False

    def flush(self):
        if self.client:
            try:
                self.client.flush()
            except Exception as exc:
                logger.error("Error flushing Langfuse: %s", exc)

    def shutdown(self):
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception as exc:
                logger.error("Error shutting down Langfuse: %s", exc)

    def create_span(
        self,
        trace,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Create a manually-ended child span for agent nodes.

        Agent nodes historically call ``create_span``/``end_span``. Langfuse
        3.x exposes ``start_span`` instead, so this adapter keeps node code
        stable while using the SDK's actual API.
        """
        if not self.client:
            return None
        try:
            parent = trace if trace is not None and hasattr(trace, "start_span") else self.client
            return parent.start_span(name=name, input=input_data, metadata=metadata or {})
        except Exception as exc:
            logger.error("Error creating span %s: %s", name, exc)
            return None

    def end_span(
        self,
        span,
        output: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not span:
            return
        try:
            update_data: Dict[str, Any] = {}
            if output is not None:
                update_data["output"] = output
            if metadata:
                update_data["metadata"] = metadata
            if update_data:
                span.update(**update_data)
            span.end()
        except Exception as exc:
            logger.error("Error ending Langfuse span: %s", exc)

    @contextmanager
    def start_generation(
        self,
        name: str,
        model: str,
        input_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self.client:
            yield None
            return

        try:
            generation = self.client.start_generation(
                name=name,
                model=model,
                input=input_data,
                metadata=metadata or {},
            )
            yield generation
        except Exception as exc:
            logger.error("Error creating generation span: %s", exc)
            yield None

    @contextmanager
    def start_span(
        self,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self.client:
            yield None
            return

        try:
            span = self.client.start_span(name=name, input=input_data, metadata=metadata or {})
            yield span
        except Exception as exc:
            logger.error("Error creating span: %s", exc)
            yield None

    def update_generation(
        self,
        generation,
        output: Any,
        usage_metadata: Optional[Dict[str, Any]] = None,
        completion_start_time: Optional[float] = None,
    ):
        if not generation:
            return

        try:
            update_data: Dict[str, Any] = {"output": output}
            if usage_metadata:
                if "prompt_tokens" in usage_metadata:
                    update_data["usage"] = {
                        "input": usage_metadata.get("prompt_tokens", 0),
                        "output": usage_metadata.get("completion_tokens", 0),
                        "total": usage_metadata.get("total_tokens", 0),
                    }
                if "latency_ms" in usage_metadata:
                    update_data["metadata"] = {"latency_ms": usage_metadata["latency_ms"]}

            generation.update(**update_data)
            generation.end()
        except Exception as exc:
            logger.error("Error updating generation: %s", exc)

    def update_span(
        self,
        span,
        output: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: Optional[str] = None,
        status_message: Optional[str] = None,
    ):
        if not span:
            return

        try:
            update_data: Dict[str, Any] = {}
            if output is not None:
                update_data["output"] = output
            if metadata:
                update_data["metadata"] = metadata
            if level:
                update_data["level"] = level
            if status_message:
                update_data["status_message"] = status_message
            if update_data:
                span.update(**update_data)
            span.end()
        except Exception as exc:
            logger.error("Error updating span: %s", exc)
