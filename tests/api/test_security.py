from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from src.config import AuthSettings
from src.security import enforce_api_security

API_KEY = "falco-test-key-0123456789-abcdef"


def _app(auth: AuthSettings, cache_client=None) -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(auth=auth)
    app.state.cache_client = cache_client
    app.middleware("http")(enforce_api_security)

    @app.get("/api/v1/protected")
    async def protected():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    return app


async def test_health_remains_public_when_auth_is_enabled():
    app = _app(AuthSettings(enabled=True, api_key=API_KEY))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200


async def test_protected_api_requires_valid_bearer_key():
    app = _app(AuthSettings(enabled=True, api_key=API_KEY))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/v1/protected")
        valid = await client.get("/api/v1/protected", headers={"Authorization": f"Bearer {API_KEY}"})
    assert missing.status_code == 401
    assert valid.status_code == 200


class _RedisCounter:
    def __init__(self):
        self.count = 0

    def eval(self, *_args):
        self.count += 1
        return self.count


async def test_rate_limit_is_enforced_after_authentication():
    redis = _RedisCounter()
    cache = SimpleNamespace(redis=redis)
    auth = AuthSettings(
        enabled=True,
        api_key=API_KEY,
        rate_limit_enabled=True,
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    app = _app(auth, cache)
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/api/v1/protected", headers=headers)
        second = await client.get("/api/v1/protected", headers=headers)
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Remaining"] == "0"
    assert second.status_code == 429
    assert "Retry-After" in second.headers


async def test_rate_limit_fails_closed_when_redis_is_unavailable():
    auth = AuthSettings(
        enabled=True,
        api_key=API_KEY,
        rate_limit_enabled=True,
        rate_limit_requests=10,
        rate_limit_window_seconds=60,
    )
    app = _app(auth, None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/protected", headers={"Authorization": f"Bearer {API_KEY}"})
    assert response.status_code == 503
