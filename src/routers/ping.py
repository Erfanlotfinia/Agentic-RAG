import asyncio
import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..dependencies import DatabaseDep, OllamaDep, OpenSearchDep, SettingsDep
from ..schemas.api.health import HealthResponse, ServiceStatus

logger = logging.getLogger(__name__)
router = APIRouter()


async def _build_health_response(
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
    ollama_client: OllamaDep,
    *,
    require_default_model: bool = False,
) -> HealthResponse:
    """Collect required dependency health without exposing internal exception details."""
    services = {}
    overall_status = "ok"

    async def check_sync_service(name: str, check_func) -> None:
        nonlocal overall_status
        try:
            result = await asyncio.to_thread(check_func)
            services[name] = result
            if result.status != "healthy":
                overall_status = "degraded"
        except Exception:
            logger.exception("Health check failed for %s", name)
            services[name] = ServiceStatus(status="unhealthy", message="Health check failed")
            overall_status = "degraded"

    def check_database() -> ServiceStatus:
        with database.get_session() as session:
            session.execute(text("SELECT 1"))
        return ServiceStatus(status="healthy", message="Connected successfully")

    def check_opensearch() -> ServiceStatus:
        if not opensearch_client.health_check():
            return ServiceStatus(status="unhealthy", message="Not responding")
        stats = opensearch_client.get_index_stats()
        if not stats.get("exists", False):
            return ServiceStatus(status="unhealthy", message="Retrieval index is unavailable")
        return ServiceStatus(
            status="healthy",
            message=f"Index '{stats.get('index_name', 'unknown')}' with {stats.get('document_count', 0)} documents",
        )

    await asyncio.gather(
        check_sync_service("database", check_database),
        check_sync_service("opensearch", check_opensearch),
    )

    try:
        ollama_health = await ollama_client.health_check()
        ollama_status = ollama_health["status"]
        ollama_message = ollama_health["message"]

        if ollama_status == "healthy" and require_default_model:
            models = await ollama_client.list_models()
            available_models = {
                value
                for item in models
                for value in (item.get("name"), item.get("model"))
                if value
            }
            if settings.ollama_model not in available_models:
                ollama_status = "unhealthy"
                ollama_message = f"Configured model '{settings.ollama_model}' is not available"

        services["ollama"] = ServiceStatus(status=ollama_status, message=ollama_message)
        if ollama_status != "healthy":
            overall_status = "degraded"
    except Exception:
        logger.exception("Health check failed for Ollama")
        services["ollama"] = ServiceStatus(status="unhealthy", message="Health check failed")
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.environment,
        service_name=settings.service_name,
        services=services,
    )


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
    ollama_client: OllamaDep,
) -> HealthResponse:
    """Report dependency health while keeping the endpoint itself available for diagnostics."""
    return await _build_health_response(settings, database, opensearch_client, ollama_client)


@router.get("/ready", response_model=HealthResponse, tags=["Health"])
async def readiness_check(
    response: Response,
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
    ollama_client: OllamaDep,
) -> HealthResponse:
    """Return 503 until all dependencies required for default RAG serving are healthy."""
    health = await _build_health_response(
        settings,
        database,
        opensearch_client,
        ollama_client,
        require_default_model=True,
    )
    if health.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
