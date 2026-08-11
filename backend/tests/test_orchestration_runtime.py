import asyncio

import pytest

from app.orchestration import (
    AgentRole,
    DelegationBudget,
    DelegationBudgetError,
    DelegationLimitError,
    DelegationPermissionError,
    DelegationRequest,
    ExecutionReport,
    MultiAgentRuntime,
    OrchestrationDisabledError,
)

ROLES = [
    AgentRole(name="coordinator", capabilities=frozenset({"read", "write"})),
    AgentRole(name="researcher", capabilities=frozenset({"read"})),
    AgentRole(name="writer", capabilities=frozenset({"write"})),
]
BUDGET = DelegationBudget(iterations=4, cost_units=100)


async def successful_executor(*_: object) -> ExecutionReport:
    return ExecutionReport(output="done", iterations_used=1, cost_units_used=10)


def runtime(**kwargs: object) -> MultiAgentRuntime:
    return MultiAgentRuntime(ROLES, successful_executor, enabled=True, **kwargs)


def request(role: str = "researcher", **kwargs: object) -> DelegationRequest:
    values = {
        "target_role": role,
        "task": "bounded task",
        "permissions": frozenset({"read"}),
        "budget": DelegationBudget(iterations=2, cost_units=50),
    }
    values.update(kwargs)
    return DelegationRequest.model_validate(values)


def test_disabled_and_root_role_permissions_are_enforced() -> None:
    disabled = MultiAgentRuntime(ROLES, successful_executor)
    with pytest.raises(OrchestrationDisabledError):
        disabled.create_root("coordinator", permissions=frozenset(), budget=BUDGET)
    with pytest.raises(DelegationPermissionError):
        runtime().create_root(
            "researcher", permissions=frozenset({"write"}), budget=BUDGET
        )


@pytest.mark.asyncio
async def test_child_cannot_amplify_permissions_or_budget() -> None:
    service = runtime()
    parent = service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    with pytest.raises(DelegationPermissionError):
        await service.delegate(
            parent,
            request("writer", permissions=frozenset({"write"})),
        )
    with pytest.raises(DelegationBudgetError):
        await service.delegate(
            parent,
            request(budget=DelegationBudget(iterations=5, cost_units=50)),
        )
    forged = parent.model_copy(update={"permissions": frozenset({"read", "write"})})
    with pytest.raises(DelegationPermissionError):
        await service.delegate(forged, request())


@pytest.mark.asyncio
async def test_depth_and_role_loops_are_rejected() -> None:
    service = runtime(max_depth=1)
    parent = service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    with pytest.raises(DelegationLimitError):
        await service.delegate(parent, request("coordinator"))

    nested_service: MultiAgentRuntime

    async def nesting_executor(context: object, *_: object) -> ExecutionReport:
        await nested_service.delegate(
            context,  # type: ignore[arg-type]
            request("writer", permissions=frozenset()),
        )
        return ExecutionReport(iterations_used=1, cost_units_used=1)

    nested_service = MultiAgentRuntime(
        ROLES, nesting_executor, enabled=True, max_depth=1
    )
    nested_parent = nested_service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    with pytest.raises(DelegationLimitError):
        await nested_service.delegate(nested_parent, request())


@pytest.mark.asyncio
async def test_concurrency_limit_is_enforced() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocking_executor(*_: object) -> ExecutionReport:
        entered.set()
        await release.wait()
        return ExecutionReport(iterations_used=1, cost_units_used=1)

    service = MultiAgentRuntime(
        ROLES, blocking_executor, enabled=True, max_concurrency=1
    )
    parent = service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    first = asyncio.create_task(service.delegate(parent, request()))
    await entered.wait()
    with pytest.raises(DelegationLimitError):
        await service.delegate(parent, request("writer", permissions=frozenset()))
    release.set()
    await first


@pytest.mark.asyncio
async def test_concurrent_children_cannot_amplify_parent_budget() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocking_executor(*_: object) -> ExecutionReport:
        entered.set()
        await release.wait()
        return ExecutionReport(iterations_used=1, cost_units_used=1)

    service = MultiAgentRuntime(ROLES, blocking_executor, enabled=True)
    parent = service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    first = asyncio.create_task(service.delegate(parent, request()))
    await entered.wait()
    with pytest.raises(DelegationBudgetError):
        await service.delegate(
            parent,
            request(budget=DelegationBudget(iterations=3, cost_units=51)),
        )
    release.set()
    await first


@pytest.mark.asyncio
async def test_cancellation_propagates_to_running_child() -> None:
    entered = asyncio.Event()

    async def cancellable_executor(
        _context: object, _task: object, cancelled: asyncio.Event
    ) -> ExecutionReport:
        entered.set()
        await cancelled.wait()
        return ExecutionReport(iterations_used=1, cost_units_used=1)

    service = MultiAgentRuntime(ROLES, cancellable_executor, enabled=True)
    parent = service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    delegated = asyncio.create_task(service.delegate(parent, request()))
    await entered.wait()
    service.cancel(parent.agent_id)
    result = await delegated
    assert result.status == "cancelled"
    assert service.active_count == 0


@pytest.mark.asyncio
async def test_reported_usage_cannot_exceed_delegated_budget() -> None:
    async def over_budget(*_: object) -> ExecutionReport:
        return ExecutionReport(iterations_used=3, cost_units_used=1)

    service = MultiAgentRuntime(ROLES, over_budget, enabled=True)
    parent = service.create_root(
        "coordinator", permissions=frozenset({"read"}), budget=BUDGET
    )
    with pytest.raises(DelegationBudgetError):
        await service.delegate(parent, request())
