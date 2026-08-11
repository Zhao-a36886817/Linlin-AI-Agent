from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.resources.models import ResourceRequest, ResourceSnapshot

T = TypeVar("T")


class ResourceGovernanceError(RuntimeError):
    pass


class ResourceOverloadError(ResourceGovernanceError):
    pass


class ResourceTimeoutError(ResourceGovernanceError):
    pass


class ResourceGovernor:
    """Bounded admission control for injected asynchronous operations."""

    def __init__(
        self,
        *,
        max_concurrency: int,
        max_queue: int,
        max_cpu_units: int,
        max_memory_bytes: int,
        provider_limits: dict[str, int] | None = None,
        queue_timeout_seconds: float = 30.0,
        execution_timeout_seconds: float = 300.0,
    ) -> None:
        limits = (max_concurrency, max_cpu_units, max_memory_bytes)
        if any(item < 1 for item in limits) or max_queue < 0:
            raise ValueError("Resource limits must be positive and queue cannot be negative.")
        if queue_timeout_seconds <= 0 or execution_timeout_seconds <= 0:
            raise ValueError("Resource timeouts must be positive.")
        if any(value < 1 for value in (provider_limits or {}).values()):
            raise ValueError("Provider concurrency limits must be positive.")
        self._max_concurrency = max_concurrency
        self._max_queue = max_queue
        self._max_cpu = max_cpu_units
        self._max_memory = max_memory_bytes
        self._provider_limits = dict(provider_limits or {})
        self._queue_timeout = queue_timeout_seconds
        self._execution_timeout = execution_timeout_seconds
        self._condition = asyncio.Condition()
        self._active = 0
        self._waiting = 0
        self._cpu = 0
        self._memory = 0
        self._providers: Counter[str] = Counter()
        self._counts: Counter[str] = Counter()
        self._peaks: Counter[str] = Counter()

    async def run(self, request: ResourceRequest, operation: Callable[[], Awaitable[T]]) -> T:
        self._validate_request(request)
        async with self._condition:
            if not self._can_admit(request):
                if self._waiting >= self._max_queue:
                    self._counts["rejected"] += 1
                    raise ResourceOverloadError("Resource queue is full.")
                self._waiting += 1
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self._can_admit(request)),
                        timeout=self._queue_timeout,
                    )
                except TimeoutError as exc:
                    self._counts["timed_out"] += 1
                    raise ResourceTimeoutError("Resource admission timed out.") from exc
                finally:
                    self._waiting -= 1
            self._admit(request)

        try:
            result = await asyncio.wait_for(operation(), timeout=self._execution_timeout)
        except TimeoutError as exc:
            self._counts["timed_out"] += 1
            raise ResourceTimeoutError("Operation execution timed out.") from exc
        except asyncio.CancelledError:
            self._counts["cancelled"] += 1
            raise
        else:
            self._counts["completed"] += 1
            return result
        finally:
            async with self._condition:
                self._release(request)
                self._condition.notify_all()

    def snapshot(self) -> ResourceSnapshot:
        return ResourceSnapshot(
            active=self._active,
            waiting=self._waiting,
            cpu_units=self._cpu,
            memory_bytes=self._memory,
            peak_active=self._peaks["active"],
            peak_cpu_units=self._peaks["cpu"],
            peak_memory_bytes=self._peaks["memory"],
            completed=self._counts["completed"],
            rejected=self._counts["rejected"],
            timed_out=self._counts["timed_out"],
            cancelled=self._counts["cancelled"],
        )

    def _validate_request(self, request: ResourceRequest) -> None:
        if request.cpu_units > self._max_cpu or request.memory_bytes > self._max_memory:
            self._counts["rejected"] += 1
            raise ResourceOverloadError("Operation exceeds the configured resource budget.")

    def _can_admit(self, request: ResourceRequest) -> bool:
        provider_limit = self._provider_limits.get(request.provider, self._max_concurrency)
        return (
            self._active < self._max_concurrency
            and self._cpu + request.cpu_units <= self._max_cpu
            and self._memory + request.memory_bytes <= self._max_memory
            and self._providers[request.provider] < provider_limit
        )

    def _admit(self, request: ResourceRequest) -> None:
        self._active += 1
        self._cpu += request.cpu_units
        self._memory += request.memory_bytes
        self._providers[request.provider] += 1
        self._peaks["active"] = max(self._peaks["active"], self._active)
        self._peaks["cpu"] = max(self._peaks["cpu"], self._cpu)
        self._peaks["memory"] = max(self._peaks["memory"], self._memory)

    def _release(self, request: ResourceRequest) -> None:
        self._active -= 1
        self._cpu -= request.cpu_units
        self._memory -= request.memory_bytes
        self._providers[request.provider] -= 1
