from typing import Dict, Optional

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    """Individual dependency status."""

    status: str = Field(..., description="Service status", examples=["healthy"])
    message: Optional[str] = Field(None, description="Status message", examples=["Connected successfully"])


class HealthResponse(BaseModel):
    """Falco health/readiness status response."""

    status: str = Field(..., description="Overall health status: ok or degraded", examples=["ok"])
    version: str = Field(..., description="Application version", examples=["1.0.0"])
    environment: str = Field(..., description="Deployment environment", examples=["development"])
    service_name: str = Field(..., description="Service identifier", examples=["falco-agentic-rag-api"])
    services: Optional[Dict[str, ServiceStatus]] = Field(None, description="Individual dependency statuses")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "environment": "development",
                "service_name": "falco-agentic-rag-api",
                "services": {
                    "database": {"status": "healthy", "message": "Connected successfully"},
                    "opensearch": {"status": "healthy", "message": "Index 'arxiv-papers-chunks' with 42 documents"},
                    "ollama": {"status": "healthy", "message": "Ollama service is running"},
                },
            }
        }
