from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.policy import (
    Identity,
    PolicyDecision,
    PolicyDeniedError,
    PolicyRequest,
    PolicyRule,
    PolicyRuntime,
)

ALLOW_READ = PolicyRule(
    rule_id="allow_reader",
    effect="allow",
    roles=frozenset({"reader"}),
    actions=frozenset({"workspace.read"}),
)


def request(**overrides: object) -> PolicyRequest:
    values = {
        "correlation_id": uuid4(),
        "identity": Identity(
            subject_id="user@example.test",
            tenant_id="tenant-a",
            roles=frozenset({"reader"}),
        ),
        "action": "workspace.read",
        "resource_tenant_id": "tenant-a",
        "workspace_tenant_id": "tenant-a",
    }
    values.update(overrides)
    return PolicyRequest.model_validate(values)


def test_default_is_least_privilege_deny() -> None:
    decision = PolicyRuntime([]).decide(request())
    assert decision.allowed is False
    assert decision.matched_rule_ids == ()


def test_explicit_allow_is_deterministic_and_audited() -> None:
    audit: list[PolicyDecision] = []
    service = PolicyRuntime([ALLOW_READ], audit_sink=audit.append)
    policy_request = request()
    first = service.decide(policy_request)
    second = service.decide(policy_request)
    assert first == second
    assert first.allowed is True
    assert audit == [first, second]


def test_deny_wins_regardless_of_rule_input_order() -> None:
    deny = PolicyRule(
        rule_id="deny_reader",
        effect="deny",
        roles=frozenset({"reader"}),
        actions=frozenset({"workspace.read"}),
    )
    for rules in ([ALLOW_READ, deny], [deny, ALLOW_READ]):
        decision = PolicyRuntime(rules).decide(request())
        assert decision.allowed is False
        assert decision.matched_rule_ids == ("deny_reader",)


@pytest.mark.parametrize(
    ("resource_tenant", "workspace_tenant"),
    [("tenant-b", "tenant-a"), ("tenant-a", "tenant-b"), ("tenant-b", "tenant-b")],
)
def test_tenant_and_workspace_isolation(
    resource_tenant: str, workspace_tenant: str
) -> None:
    decision = PolicyRuntime([ALLOW_READ]).decide(
        request(
            resource_tenant_id=resource_tenant,
            workspace_tenant_id=workspace_tenant,
        )
    )
    assert decision.allowed is False
    assert "boundary" in decision.reason


def test_action_and_role_are_exact_not_implicitly_administrative() -> None:
    service = PolicyRuntime([ALLOW_READ])
    no_role = Identity(subject_id="owner", tenant_id="tenant-a", roles=frozenset())
    assert service.decide(request(identity=no_role)).allowed is False
    assert service.decide(request(action="workspace.write")).allowed is False


def test_require_blocks_before_caller_can_execute() -> None:
    with pytest.raises(PolicyDeniedError) as captured:
        PolicyRuntime([]).require(request())
    assert captured.value.decision.allowed is False


def test_identity_contract_rejects_credential_fields() -> None:
    with pytest.raises(ValidationError):
        Identity.model_validate(
            {
                "subject_id": "user",
                "tenant_id": "tenant-a",
                "roles": [],
                "api_key": "must-not-enter-policy",
            }
        )
