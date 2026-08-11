from fastapi.testclient import TestClient

from app.api.contracts import (
    API_STABILITY_HEADER,
    API_VERSION_HEADER,
    DEPRECATION_MIN_DAYS,
    DEPRECATION_MIN_MINOR_RELEASES,
    PUBLIC_API_OWNERS,
    PUBLIC_API_SUPPORTED_VERSIONS,
    PUBLIC_API_VERSION,
    public_api_owner,
)
from app.main import app

client = TestClient(app)


def test_legacy_client_defaults_to_current_contract() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers[API_VERSION_HEADER] == PUBLIC_API_VERSION
    assert response.headers[API_STABILITY_HEADER] == "stable"
    assert API_VERSION_HEADER.lower() in response.headers["vary"].lower()


def test_current_contract_can_be_requested_explicitly() -> None:
    response = client.get(
        "/api/health",
        headers={API_VERSION_HEADER: PUBLIC_API_VERSION},
    )

    assert response.status_code == 200
    assert response.headers[API_VERSION_HEADER] == PUBLIC_API_VERSION


def test_unknown_contract_requires_versioned_migration() -> None:
    response = client.get(
        "/api/health",
        headers={API_VERSION_HEADER: "2"},
    )

    assert response.status_code == 406
    assert response.json() == {
        "detail": "Requested public API version is not supported.",
        "requested_version": "2",
        "supported_versions": list(PUBLIC_API_SUPPORTED_VERSIONS),
    }
    assert response.headers[API_VERSION_HEADER] == PUBLIC_API_VERSION


def test_published_deprecation_window_is_stable() -> None:
    assert DEPRECATION_MIN_MINOR_RELEASES == 2
    assert DEPRECATION_MIN_DAYS == 90


def test_contract_headers_are_added_to_validation_errors() -> None:
    response = client.post("/api/chat", json={})

    assert response.status_code == 422
    assert response.headers[API_VERSION_HEADER] == PUBLIC_API_VERSION


def test_non_api_routes_are_not_part_of_the_public_contract() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert API_VERSION_HEADER not in response.headers


def test_every_published_openapi_route_has_an_owner() -> None:
    public_paths = {
        path for path in app.openapi()["paths"] if path.startswith("/api/")
    }
    unowned = sorted(path for path in public_paths if public_api_owner(path) is None)

    assert public_paths
    assert not unowned
    assert set(PUBLIC_API_OWNERS.values())
