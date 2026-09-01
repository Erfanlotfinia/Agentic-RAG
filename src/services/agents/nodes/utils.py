import json
import logging
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ..models import ReasoningStep, SourceItem, ToolArtefact

logger = logging.getLogger(__name__)


def _parse_tool_documents(message: ToolMessage) -> List[Dict]:
    if getattr(message, "name", None) != "retrieve_papers":
        return []

    content = message.content if hasattr(message, "content") else ""
    if not isinstance(content, str):
        return []

    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return []

    documents = payload.get("documents", []) if isinstance(payload, dict) else []
    return documents if isinstance(documents, list) else []


def get_latest_retrieved_documents(messages: List) -> List[Dict]:
    """Return documents from the most recent retrieve_papers tool call."""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            documents = _parse_tool_documents(msg)
            if documents or getattr(msg, "name", None) == "retrieve_papers":
                return documents
    return []


def extract_sources_from_tool_messages(messages: List) -> List[SourceItem]:
    """Extract deduplicated sources from the most recent retrieval result."""
    documents = get_latest_retrieved_documents(messages)
    sources: List[SourceItem] = []
    seen_ids = set()

    for document in documents:
        metadata = document.get("metadata", {}) if isinstance(document, dict) else {}
        arxiv_id = str(metadata.get("arxiv_id", ""))
        if not arxiv_id or arxiv_id in seen_ids:
            continue

        authors = metadata.get("authors", [])
        if isinstance(authors, str):
            authors = [author.strip() for author in authors.split(",") if author.strip()]
        elif not isinstance(authors, list):
            authors = []

        sources.append(
            SourceItem(
                arxiv_id=arxiv_id,
                title=str(metadata.get("title", "")),
                authors=[str(author) for author in authors],
                url=str(metadata.get("source", "")),
                relevance_score=float(metadata.get("score", 0.0) or 0.0),
            )
        )
        seen_ids.add(arxiv_id)

    return sources


def extract_tool_artefacts(messages: List) -> List[ToolArtefact]:
    """Extract tool artifacts from messages."""
    artefacts = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            parsed_content = _parse_tool_documents(msg) or msg.content
            artefacts.append(
                ToolArtefact(
                    tool_name=getattr(msg, "name", "unknown"),
                    tool_call_id=getattr(msg, "tool_call_id", ""),
                    content=parsed_content,
                    metadata={},
                )
            )

    return artefacts


def create_reasoning_step(
    step_name: str,
    description: str,
    metadata: Optional[Dict] = None,
) -> ReasoningStep:
    """Create a reasoning step record."""
    return ReasoningStep(
        step_name=step_name,
        description=description,
        metadata=metadata or {},
    )


def filter_messages(messages: List) -> List[AIMessage | HumanMessage]:
    """Filter messages to user/assistant messages."""
    return [msg for msg in messages if isinstance(msg, (HumanMessage, AIMessage))]


def get_latest_query(messages: List) -> str:
    """Get the latest user query from messages."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content

    raise ValueError("No user query found in messages")


def get_latest_context(messages: List) -> str:
    """Get clean text context from the latest retrieval tool message."""
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            continue

        documents = _parse_tool_documents(msg)
        if documents:
            rendered = []
            for document in documents:
                metadata = document.get("metadata", {})
                title = metadata.get("title", "Untitled")
                arxiv_id = metadata.get("arxiv_id", "unknown")
                content = document.get("page_content", "")
                rendered.append(f"[{title} | arXiv:{arxiv_id}]\n{content}")
            return "\n\n".join(rendered)

        # Backward-compatible fallback for legacy/raw ToolMessage content used in tests.
        return msg.content if hasattr(msg, "content") else ""

    return ""
