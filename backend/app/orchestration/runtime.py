from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from app.orchestration.models import (
    AgentContext,
    AgentRole,
    DelegationBudget,
    DelegationRequest,
    DelegationResult,
    ExecutionReport,
)

AgentExecutor = Callable[[AgentContext, str, asyncio.Event], Awaitable[ExecutionReport]]


class OrchestrationError(RuntimeError):
    pass


class OrchestrationDisabledError(OrchestrationError):
    pass


class DelegationPermissionError(OrchestrationError):
    pass


class DelegationLimitError(OrchestrationError):
    pass


class DelegationBudgetError(OrchestrationError):
    pass


class MultiAgentRuntime:
    """Runs bounded injected agents without granting provider or tool privileges."""

    def __init__(
        self,
        roles: list[AgentRole],
        executor: AgentExecutor,
        *,
        enabled: bool = False,
        max_depth: int = 2,
        max_concurrency: int = 4,
    ) -> None:
        if max_depth < 1 or max_concurrency < 1:
            raise ValueError("Delegation limits must be positive.")
        self.enabled = enabled
        self._roles = {role.name: role for role in roles}
        if len(self._roles) != len(roles):
            raise ValueError("Role names must be unique.")
        self._executor = executor
        self._max_depth = max_depth
        self._max_concurrency = max_concurrency
        self._active: dict[UUID, asyncio.Event] = {}
        self._children: dict[UUID, set[UUID]] = {}
        self._contexts: dict[UUID, AgentContext] = {}
        self._remaining: dict[UUID, list[int]] = {}

    def create_root(
        self,
        role: str,
        *,
        permissions: frozenset[str],
        budget: DelegationBudget,
    ) -> AgentContext:
        self._require_enabled()
        definition = self._role(role)
        if not permissions <= definition.capabilities:
            raise DelegationPermissionError("Root permissions exceed the role capabilities.")
        context = AgentContext(
            agent_id=uuid4(),
            role=role,
            permissions=permissions,
            budget=budget,
            depth=0,
            role_path=(role,),
        )
        self._contexts[context.agent_id] = context
        self._remaining[context.agent_id] = [budget.iterations, budget.cost_units]
        return context

    async def delegate(
        self, parent: AgentContext, request: DelegationRequest
    ) -> DelegationResult:
        self._require_enabled()
        if self._contexts.get(parent.agent_id) != parent:
            raise DelegationPermissionError("Caller context is not registered.")
        role = self._role(request.target_role)
        if request.target_role in parent.role_path:
            raise DelegationLimitError("Delegation role loop detected.")
        if parent.depth + 1 > self._max_depth:
            raise DelegationLimitError("Maximum delegation depth exceeded.")
        if len(self._active) >= self._max_concurrency:
            raise DelegationLimitError("Maximum delegation concurrency reached.")
        if not request.permissions <= parent.permissions:
            raise DelegationPermissionError("Child permissions exceed caller permissions.")
        if not request.permissions <= role.capabilities:
            raise DelegationPermissionError("Child permissions exceed target role capabilities.")
        remaining = self._remaining[parent.agent_id]
        if (
            request.budget.iterations > remaining[0]
            or request.budget.cost_units > remaining[1]
        ):
            raise DelegationBudgetError("Child budget exceeds caller budget.")
        remaining[0] -= request.budget.iterations
        remaining[1] -= request.budget.cost_units

        child = AgentContext(
            agent_id=uuid4(),
            role=role.name,
            permissions=request.permissions,
            budget=request.budget,
            depth=parent.depth + 1,
            role_path=(*parent.role_path, role.name),
        )
        cancelled = asyncio.Event()
        self._active[child.agent_id] = cancelled
        self._children.setdefault(parent.agent_id, set()).add(child.agent_id)
        self._contexts[child.agent_id] = child
        self._remaining[child.agent_id] = [
            child.budget.iterations,
            child.budget.cost_units,
        ]
        try:
            report = await self._executor(child, request.task, cancelled)
            if (
                report.iterations_used > child.budget.iterations
                or report.cost_units_used > child.budget.cost_units
            ):
                raise DelegationBudgetError("Agent exceeded its delegated budget.")
            remaining[0] += child.budget.iterations - report.iterations_used
            remaining[1] += child.budget.cost_units - report.cost_units_used
            return DelegationResult(
                agent_id=child.agent_id,
                status="cancelled" if cancelled.is_set() else "completed",
                output=None if cancelled.is_set() else report.output,
                iterations_used=report.iterations_used,
                cost_units_used=report.cost_units_used,
            )
        finally:
            self._active.pop(child.agent_id, None)
            self._children.get(parent.agent_id, set()).discard(child.agent_id)
            self._contexts.pop(child.agent_id, None)
            self._remaining.pop(child.agent_id, None)

    def cancel(self, agent_id: UUID) -> None:
        event = self._active.get(agent_id)
        if event is not None:
            event.set()
        for child_id in tuple(self._children.get(agent_id, ())):
            self.cancel(child_id)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def _role(self, name: str) -> AgentRole:
        try:
            return self._roles[name]
        except KeyError as exc:
            raise DelegationPermissionError(f"Unknown agent role '{name}'.") from exc

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise OrchestrationDisabledError("Multi-agent orchestration is disabled.")
