from __future__ import annotations

from collections.abc import Callable

from app.policy.models import PolicyDecision, PolicyRequest, PolicyRule

AuditSink = Callable[[PolicyDecision], None]


class PolicyDeniedError(PermissionError):
    def __init__(self, decision: PolicyDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


class PolicyRuntime:
    """Deterministic, deny-by-default authorization before privileged execution."""

    def __init__(self, rules: list[PolicyRule], *, audit_sink: AuditSink | None = None) -> None:
        if len({rule.rule_id for rule in rules}) != len(rules):
            raise ValueError("Policy rule identifiers must be unique.")
        self._rules = tuple(sorted(rules, key=lambda item: item.rule_id))
        self._audit_sink = audit_sink

    def decide(self, request: PolicyRequest) -> PolicyDecision:
        if not self._tenant_aligned(request):
            return self._record(request, False, "Tenant or workspace boundary mismatch.")

        matching = tuple(rule for rule in self._rules if self._matches(rule, request))
        denied = tuple(rule.rule_id for rule in matching if rule.effect == "deny")
        if denied:
            return self._record(request, False, "Explicit deny rule matched.", denied)
        allowed = tuple(rule.rule_id for rule in matching if rule.effect == "allow")
        if allowed:
            return self._record(request, True, "Explicit allow rule matched.", allowed)
        return self._record(request, False, "No allow rule matched.")

    def require(self, request: PolicyRequest) -> PolicyDecision:
        decision = self.decide(request)
        if not decision.allowed:
            raise PolicyDeniedError(decision)
        return decision

    @staticmethod
    def _tenant_aligned(request: PolicyRequest) -> bool:
        return (
            request.identity.tenant_id
            == request.resource_tenant_id
            == request.workspace_tenant_id
        )

    @staticmethod
    def _matches(rule: PolicyRule, request: PolicyRequest) -> bool:
        return (
            request.action in rule.actions
            and bool(request.identity.roles & rule.roles)
            and (not rule.tenant_ids or request.identity.tenant_id in rule.tenant_ids)
        )

    def _record(
        self,
        request: PolicyRequest,
        allowed: bool,
        reason: str,
        matched: tuple[str, ...] = (),
    ) -> PolicyDecision:
        decision = PolicyDecision(
            correlation_id=request.correlation_id,
            subject_id=request.identity.subject_id,
            tenant_id=request.identity.tenant_id,
            action=request.action,
            allowed=allowed,
            reason=reason,
            matched_rule_ids=matched,
        )
        if self._audit_sink is not None:
            self._audit_sink(decision)
        return decision
