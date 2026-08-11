from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.runtime_control import memory_runtime
from app.main import app

client = TestClient(app)


def enable_memory(enabled: bool) -> None:
    phrase = "ENABLE MEMORY" if enabled else "DISABLE MEMORY"
    response = client.put(
        "/api/runtime-control/memory/enabled",
        json={"enabled": enabled, "confirmation": phrase},
    )
    assert response.status_code == 200


def test_overview_is_honest_about_advanced_runtime_product_wiring() -> None:
    response = client.get("/api/runtime-control")
    assert response.status_code == 200
    features = {item["key"]: item for item in response.json()["features"]}
    assert features["memory"]["configured"] is True
    for key in ("rag", "mcp"):
        assert features[key]["configured"] is False
        assert features[key]["status"] == "setup_required"
    assert features["orchestration"]["configured"] is True
    assert features["orchestration"]["status"] == "ready"
    assert features["scheduler"]["configured"] is True
    assert features["scheduler"]["status"] == "disabled"


def test_memory_enable_requires_exact_confirmation() -> None:
    previous = memory_runtime.enabled
    response = client.put(
        "/api/runtime-control/memory/enabled",
        json={"enabled": True, "confirmation": "yes"},
    )
    assert response.status_code == 422
    assert memory_runtime.enabled is previous
    assert response.json()["detail"].startswith("Type ENABLE")


def test_memory_records_require_owner_scope_and_consent() -> None:
    enable_memory(True)
    assert client.get("/api/runtime-control/memory/records").status_code == 422
    response = client.post(
        "/api/runtime-control/memory/records",
        headers={"X-Linlin-Owner": "owner-a"},
        json={"content": "prefers concise replies", "session_id": "session-a", "consent": False},
    )
    assert response.status_code == 422


def test_memory_create_list_delete_and_isolation() -> None:
    enable_memory(True)
    session = f"session-{uuid4()}"
    created = client.post(
        "/api/runtime-control/memory/records",
        headers={"X-Linlin-Owner": "owner-a"},
        json={"content": "prefers concise replies", "session_id": session, "consent": True},
    )
    assert created.status_code == 201
    record_id = created.json()["id"]
    own = client.get(
        "/api/runtime-control/memory/records",
        headers={"X-Linlin-Owner": "owner-a"},
        params={"session_id": session},
    )
    other = client.get(
        "/api/runtime-control/memory/records",
        headers={"X-Linlin-Owner": "owner-b"},
        params={"session_id": session},
    )
    assert [item["id"] for item in own.json()] == [record_id]
    assert other.json() == []
    deleted = client.delete(
        f"/api/runtime-control/memory/records/{record_id}",
        headers={"X-Linlin-Owner": "owner-a"},
        params={"session_id": session},
    )
    assert deleted.status_code == 204


def test_memory_rejects_credential_like_content_without_echoing_it() -> None:
    enable_memory(True)
    secret = "api_key=x"
    response = client.post(
        "/api/runtime-control/memory/records",
        headers={"X-Linlin-Owner": "owner-a"},
        json={"content": secret, "consent": True},
    )
    assert response.status_code == 422
    assert secret not in response.text
