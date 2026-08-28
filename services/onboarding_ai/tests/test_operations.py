import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


class FakeRedis:
    def __init__(self, healthy=True):
        self.healthy = healthy

    async def ping(self):
        if not self.healthy:
            raise ConnectionError("offline")
        return True


class FakeQdrant:
    def __init__(self, healthy=True):
        self.healthy = healthy

    async def get_collections(self):
        if not self.healthy:
            raise ConnectionError("offline")
        return []


def make_settings(**values):
    return Settings(
        service_token="x" * 32,
        **values,
    )


def test_health_endpoint_does_not_depend_on_backends():
    app = create_app(make_settings(), FakeRedis(False), FakeQdrant(False))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "onboarding-ai"}


def test_ready_reports_all_dependencies():
    app = create_app(make_settings(), FakeRedis(), FakeQdrant())
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"redis": True, "qdrant": True},
    }


def test_ready_fails_without_leaking_connection_details():
    app = create_app(make_settings(), FakeRedis(False), FakeQdrant())
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"redis": False, "qdrant": True},
    }
    assert "offline" not in response.text


@pytest.mark.parametrize(
    "values",
    [
        {"service_token": "short"},
        {"llm_provider": "ollama"},
        {"llm_provider": "openai", "llm_api_url": "https://llm.invalid"},
    ],
)
def test_invalid_security_or_provider_configuration_is_rejected(values):
    with pytest.raises(ValidationError):
        Settings(**values)
