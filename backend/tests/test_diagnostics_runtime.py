import json

from app.diagnostics import DiagnosticsRuntime


def test_known_and_pattern_secrets_never_appear_in_event_or_bundle() -> None:
    runtime = DiagnosticsRuntime(known_secrets=["private-value"])
    correlation = runtime.correlation_id()
    runtime.emit(
        correlation_id=correlation,
        component="provider.runtime",
        code="CALL_FAILED",
        severity="error",
        summary="token=private-value bearer abc.def sk-abcdefghijk",
        actor="private-value",
        attributes={
            "nested": {"api_key": "private-value"},
            "detail": "password=hunter2",
            "private-value-key": "safe",
        },
    )
    exported = json.dumps(runtime.bundle())
    for secret in ("private-value", "abc.def", "sk-abcdefghijk", "hunter2"):
        assert secret not in exported
    assert "[REDACTED]" in exported


def test_private_content_keys_are_redacted_by_default() -> None:
    runtime = DiagnosticsRuntime()
    event = runtime.emit(
        correlation_id=runtime.correlation_id(),
        component="agent.runtime",
        code="REQUEST_RECEIVED",
        severity="info",
        summary="request metadata accepted",
        attributes={"prompt": "private prompt", "content": "private file"},
    )
    assert event.attributes == {"prompt": "[REDACTED]", "content": "[REDACTED]"}


def test_retention_is_bounded_but_health_counts_are_cumulative() -> None:
    runtime = DiagnosticsRuntime(retention=2)
    correlation = runtime.correlation_id()
    for index in range(3):
        runtime.emit(
            correlation_id=correlation,
            component="agent.runtime",
            code=f"EVENT_{index}",
            severity="info",
            summary=f"event {index}",
        )
    assert [event.code for event in runtime.events()] == ["EVENT_1", "EVENT_2"]
    assert runtime.health().total_events == 3
    assert runtime.health().retained_events == 2


def test_correlation_filters_related_events() -> None:
    runtime = DiagnosticsRuntime()
    first = runtime.correlation_id()
    second = runtime.correlation_id()
    for correlation in (first, first, second):
        runtime.emit(
            correlation_id=correlation,
            component="tool.runtime",
            code="TOOL_RESULT",
            severity="info",
            summary="tool completed",
        )
    assert len(runtime.events(correlation_id=first)) == 2
    assert len(runtime.events(correlation_id=second)) == 1


def test_failure_diagnostic_explains_type_without_leaking_secret() -> None:
    runtime = DiagnosticsRuntime(known_secrets=["secret-token"])
    event = runtime.record_failure(
        correlation_id=runtime.correlation_id(),
        component="provider.runtime",
        code="PROVIDER_FAILED",
        error=RuntimeError("request rejected for secret-token"),
    )
    assert "RuntimeError" in event.summary
    assert "secret-token" not in event.summary
    assert event.attributes["exception_type"] == "RuntimeError"


def test_bundle_is_json_safe_and_contains_health_snapshot() -> None:
    runtime = DiagnosticsRuntime()
    runtime.emit(
        correlation_id=runtime.correlation_id(),
        component="workspace.runtime",
        code="PATH_REJECTED",
        severity="warning",
        summary="workspace path rejected",
    )
    bundle = runtime.bundle()
    json.dumps(bundle)
    assert bundle["health"]["warning_events"] == 1
