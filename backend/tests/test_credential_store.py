import pytest

from app.security.credential_models import REDACTED, redact_secrets
from app.security.credential_store import (
    CredentialNotFoundError,
    CredentialStore,
    SessionCredentialBackend,
)


def test_session_fallback_is_explicitly_non_persistent() -> None:
    store = CredentialStore(environment={})
    store.set("API_KEY", "test-value")
    assert store.persistent is False
    assert store.get("API_KEY") == "test-value"
    assert CredentialStore(environment={}).has("API_KEY") is False


def test_environment_reference_remains_compatible_without_persistence() -> None:
    store = CredentialStore(environment={"API_KEY": "environment-value"})
    assert store.has("API_KEY") is True
    assert store.get("API_KEY") == "environment-value"


def test_missing_credential_fails_predictably() -> None:
    with pytest.raises(CredentialNotFoundError, match="unavailable"):
        CredentialStore(environment={}).get("MISSING")


def test_injected_secure_backend_reports_persistence() -> None:
    backend = SessionCredentialBackend()
    backend.persistent = True
    backend.name = "test-secure-backend"
    store = CredentialStore(backend=backend, environment={})
    assert store.persistent is True


def test_redaction_removes_secrets_from_nested_diagnostics() -> None:
    known_value = "test-secret-value"
    diagnostic = {"message": f"failed with {known_value}", "items": [known_value]}
    assert redact_secrets(diagnostic, [known_value]) == {
        "message": f"failed with {REDACTED}",
        "items": [REDACTED],
    }
