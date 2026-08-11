import asyncio
from time import perf_counter

import pytest

from app.resources import (
    ResourceGovernor,
    ResourceOverloadError,
    ResourceRequest,
    ResourceTimeoutError,
)

REQUEST = ResourceRequest(provider="local.test", cpu_units=1, memory_bytes=10)


def governor(**overrides: object) -> ResourceGovernor:
    values = {
        "max_concurrency": 2,
        "max_queue": 4,
        "max_cpu_units": 2,
        "max_memory_bytes": 20,
        "queue_timeout_seconds": 1.0,
        "execution_timeout_seconds": 1.0,
    }
    values.update(overrides)
    return ResourceGovernor(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_load_is_bounded_and_measurable() -> None:
    service = governor()

    async def operation() -> int:
        await asyncio.sleep(0.01)
        return 1

    results = await asyncio.gather(*(service.run(REQUEST, operation) for _ in range(6)))
    snapshot = service.snapshot()
    assert sum(results) == 6
    assert snapshot.completed == 6
    assert snapshot.peak_active == 2
    assert snapshot.peak_cpu_units == 2
    assert snapshot.peak_memory_bytes == 20
    assert snapshot.active == snapshot.waiting == 0


@pytest.mark.asyncio
async def test_full_queue_rejects_predictably() -> None:
    service = governor(max_concurrency=1, max_queue=1, max_cpu_units=1)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked() -> None:
        entered.set()
        await release.wait()

    first = asyncio.create_task(service.run(REQUEST, blocked))
    await entered.wait()
    second = asyncio.create_task(service.run(REQUEST, blocked))
    await asyncio.sleep(0)
    with pytest.raises(ResourceOverloadError):
        await service.run(REQUEST, blocked)
    release.set()
    await asyncio.gather(first, second)
    assert service.snapshot().rejected == 1


@pytest.mark.asyncio
async def test_single_request_over_resource_budget_is_rejected() -> None:
    service = governor()
    oversized = ResourceRequest(provider="local.test", cpu_units=3, memory_bytes=10)
    with pytest.raises(ResourceOverloadError):
        await service.run(oversized, _complete)


@pytest.mark.asyncio
async def test_provider_concurrency_limit_serializes_provider() -> None:
    service = governor(provider_limits={"cloud.test": 1})
    request = ResourceRequest(provider="cloud.test", cpu_units=1, memory_bytes=1)
    active = 0
    peak = 0

    async def operation() -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1

    await asyncio.gather(*(service.run(request, operation) for _ in range(4)))
    assert peak == 1


@pytest.mark.asyncio
async def test_execution_timeout_releases_resources() -> None:
    service = governor(execution_timeout_seconds=0.01)

    async def slow() -> None:
        await asyncio.sleep(1)

    with pytest.raises(ResourceTimeoutError):
        await service.run(REQUEST, slow)
    snapshot = service.snapshot()
    assert snapshot.timed_out == 1
    assert snapshot.active == snapshot.cpu_units == snapshot.memory_bytes == 0


@pytest.mark.asyncio
async def test_cancellation_releases_resources() -> None:
    service = governor()
    entered = asyncio.Event()

    async def blocked() -> None:
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(service.run(REQUEST, blocked))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service.snapshot().cancelled == 1
    assert service.snapshot().active == 0


@pytest.mark.asyncio
async def test_queued_cancellation_releases_waiting_slot() -> None:
    service = governor(max_concurrency=1, max_queue=1, max_cpu_units=1)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked() -> None:
        entered.set()
        await release.wait()

    active = asyncio.create_task(service.run(REQUEST, blocked))
    await entered.wait()
    queued = asyncio.create_task(service.run(REQUEST, _complete))
    await asyncio.sleep(0)
    assert service.snapshot().waiting == 1
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    assert service.snapshot().waiting == 0
    release.set()
    await active


@pytest.mark.asyncio
async def test_short_soak_releases_every_admission() -> None:
    service = governor(max_queue=10)
    for _ in range(20):
        await asyncio.gather(*(service.run(REQUEST, _complete) for _ in range(4)))
    snapshot = service.snapshot()
    assert snapshot.completed == 80
    assert snapshot.active == snapshot.waiting == 0


@pytest.mark.asyncio
async def test_admission_overhead_benchmark() -> None:
    service = governor()
    started = perf_counter()
    for _ in range(100):
        await service.run(REQUEST, _complete)
    elapsed = perf_counter() - started
    assert elapsed < 5.0
    assert service.snapshot().completed == 100


async def _complete() -> None:
    await asyncio.sleep(0)
