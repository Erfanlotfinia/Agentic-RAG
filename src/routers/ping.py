import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..dependencies import DatabaseDep, OpenSearchDep, SettingsDep
from ..schemas.api.health import HealthResponse, ServiceStatus
from ..services.ollama import OllamaClient

logger = logging.getLogger(__name__)
router = APIRouter()


async def _build_health_response(
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
) -> HealthResponse:
    """Collect required dependency health without exposing internal exception details."""
    services = {}
    overall_status = "ok"

    def check_service(name: str, check_func) -> None:
        nonlocal overall_status
        try:
            result = check_func()
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
        return ServiceStatus(
            status="healthy",
            message=f"Index '{stats.get('index_name', 'unknown')}' with {stats.get('document_count', 0)} documents",
        )

    check_service("database", check_database)
    check_service("opensearch", check_opensearch)

    try:
        ollama_client = OllamaClient(settings)
        ollama_health = await ollama_client.health_check()
        services["ollama"] = ServiceStatus(status=ollama_health["status"], message=ollama_health["message"])
        if ollama_health["status"] != "healthy":
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
) -> HealthResponse:
    """Report dependency health while keeping the endpoint itself available for diagnostics."""
    return await _build_health_response(settings, database, opensearch_client)


@router.get("/ready", response_model=HealthResponse, tags=["Health"])
async def readiness_check(
    response: Response,
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
) -> HealthResponse:
    """Return 503 until all dependencies required for core RAG serving are healthy."""
    health = await _build_health_response(settings, database, opensearch_client)
    if health.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
