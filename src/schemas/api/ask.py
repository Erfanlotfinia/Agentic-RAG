from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

Category = Annotated[str, Field(min_length=1, max_length=32)]


class AskRequest(BaseModel):
    """Request model for RAG question answering."""

    query: str = Field(..., description="User's question", min_length=1, max_length=1000)
    top_k: int = Field(3, description="Number of top chunks to retrieve", ge=1, le=10)
    use_hybrid: bool = Field(True, description="Use hybrid search (BM25 + vector)")
    model: str = Field("llama3.2:1b", description="Ollama model to use for generation", min_length=1, max_length=128)
    categories: Optional[List[Category]] = Field(
        None,
        description="Filter by arXiv categories",
        max_length=20,
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional conversation identifier used by Agentic RAG to keep thread state across requests",
        min_length=1,
        max_length=128,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "top_k": 3,
                "use_hybrid": True,
                "model": "llama3.2:1b",
                "categories": ["cs.AI", "cs.LG"],
                "session_id": "research-session-1",
            }
        }


class AskResponse(BaseModel):
    """Response model for RAG question answering."""

    query: str = Field(..., description="Original user question")
    answer: str = Field(..., description="Generated answer from LLM")
    sources: List[str] = Field(..., description="PDF URLs of source papers")
    chunks_used: int = Field(..., description="Number of chunks used for generation")
    search_mode: str = Field(..., description="Search mode used: bm25 or hybrid")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "answer": "Transformers are a neural network architecture...",
                "sources": ["https://arxiv.org/pdf/1706.03762.pdf", "https://arxiv.org/pdf/1810.04805.pdf"],
                "chunks_used": 3,
                "search_mode": "hybrid",
            }
        }


class AgenticAskResponse(AskResponse):
    """Response model for Agentic RAG question answering."""

    reasoning_steps: List[str] = Field(..., description="Compact execution summary")
    retrieval_attempts: int = Field(..., description="Number of document retrieval attempts")
    rewritten_query: Optional[str] = Field(None, description="Latest rewritten retrieval query, when query rewriting occurred")
    session_id: Optional[str] = Field(None, description="Conversation session identifier used for this Agentic request")
    trace_id: Optional[str] = Field(None, description="Langfuse trace ID for feedback and debugging")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "answer": "Transformers are neural network architectures...",
                "sources": ["https://arxiv.org/pdf/1706.03762.pdf"],
                "chunks_used": 3,
                "search_mode": "hybrid",
                "reasoning_steps": [
                    "Validated query scope (score: 95/100)",
                    "Retrieved documents (1 attempt(s))",
                    "Graded documents (1 relevant)",
                    "Generated answer from context",
                ],
                "retrieval_attempts": 1,
                "rewritten_query": None,
                "session_id": "research-session-1",
                "trace_id": "abc123-def456-ghi789",
            }
        }


class FeedbackRequest(BaseModel):
    """Request model for user feedback on RAG answers."""

    trace_id: str = Field(..., description="Langfuse trace ID from the response", min_length=1, max_length=256)
    score: float = Field(..., description="Feedback score (0-1 or -1 to 1)", ge=-1, le=1)
    comment: Optional[str] = Field(None, description="Optional feedback comment", max_length=1000)

    class Config:
        json_schema_extra = {
            "example": {
                "trace_id": "abc123-def456-ghi789",
                "score": 1.0,
                "comment": "This answer was very helpful and accurate!",
            }
        }


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    success: bool = Field(..., description="Whether feedback was recorded successfully")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Feedback recorded successfully",
            }
        }
