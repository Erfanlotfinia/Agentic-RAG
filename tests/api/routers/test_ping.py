async def test_health_check(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service_name" in data
    assert "version" in data
    assert "services" in data


async def test_readiness_check_is_healthy_when_required_dependencies_are_available(client):
    response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
