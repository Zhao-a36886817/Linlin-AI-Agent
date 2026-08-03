from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_agent_status() -> None:
    response = client.get("/api/agents/status")

    assert response.status_code == 200
    assert response.json()["runtime_status"] == "idle"
