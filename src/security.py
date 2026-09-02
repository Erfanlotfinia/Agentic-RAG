import asyncio
import hashlib
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse, Response

PUBLIC_API_PATHS = {"/api/v1/health", "/api/v1/ready"}


async def enforce_api_security(request: Request, call_next) -> Response:
    """Protect Falco API routes with optional bearer authentication and rate limits."""
    settings = getattr(request.app.state, "settings", None)
    if settings is None or not request.url.path.startswith("/api/") or request.url.path in PUBLIC_API_PATHS:
        return await call_next(request)

    auth = settings.auth
    if not auth.enabled:
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    scheme, _, supplied_key = authorization.partition(" ")
    expected_key = auth.api_key.get_secret_value()
    if scheme.lower() != "bearer" or not supplied_key or not secrets.compare_digest(supplied_key, expected_key):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    rate_headers: dict[str, str] = {}
    if auth.rate_limit_enabled:
        cache_client = getattr(request.app.state, "cache_client", None)
        if cache_client is None:
            return JSONResponse(status_code=503, content={"detail": "Rate-limit service is unavailable"})

        window = auth.rate_limit_window_seconds
        bucket = int(time.time() // window)
        identity_hash = hashlib.sha256(supplied_key.encode()).hexdigest()[:16]
        key = f"api_rate_limit:v1:{identity_hash}:{bucket}"
        script = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        return current
        """
        try:
            current = int(await asyncio.to_thread(cache_client.redis.eval, script, 1, key, window + 1))
        except Exception:
            return JSONResponse(status_code=503, content={"detail": "Rate-limit service is unavailable"})

        remaining = max(0, auth.rate_limit_requests - current)
        rate_headers = {
            "X-RateLimit-Limit": str(auth.rate_limit_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str((bucket + 1) * window),
        }
        if current > auth.rate_limit_requests:
            retry_after = max(1, (bucket + 1) * window - int(time.time()))
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={**rate_headers, "Retry-After": str(retry_after)},
            )

    response = await call_next(request)
    for header, value in rate_headers.items():
        response.headers[header] = value
    return response
