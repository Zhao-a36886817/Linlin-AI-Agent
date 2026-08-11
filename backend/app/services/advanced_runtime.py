from __future__ import annotations

import asyncio
import ipaddress
import json
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx

from app.core.config import Settings, get_settings
from app.mcp import McpRuntime, McpTool
from app.orchestration import (
    AgentContext,
    AgentRole,
    DelegationBudget,
    DelegationRequest,
    ExecutionReport,
    MultiAgentRuntime,
)
from app.providers.manager import ProviderManager, provider_manager
from app.rag import ProviderEmbeddingBackend, RagRuntime
from app.rag.loader import WorkspaceTextLoader
from app.scheduler import SchedulerRuntime
from app.tools.manager import ToolManager
from app.workspace import WorkspaceRuntime


class AdvancedRuntimeError(RuntimeError):
    pass


class McpHttpTransport:
    """Minimal MCP Streamable HTTP transport restricted to loopback hosts."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AdvancedRuntimeError("MCP endpoint must be an HTTP URL.")
        if parsed.hostname != "localhost":
            try:
                if not ipaddress.ip_address(parsed.hostname).is_loopback:
                    raise AdvancedRuntimeError(
                        "P26 allows loopback MCP endpoints only.",
                    )
            except ValueError as exc:
                raise AdvancedRuntimeError(
                    "P26 allows loopback MCP endpoints only.",
                ) from exc
        self.endpoint = endpoint
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._request_id = 0
        self._session_id: str | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "linlin-agent", "version": "0.1.0"},
            },
        )
        await self._notification("notifications/initialized")
        self._initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.initialize()
        result = await self._request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise AdvancedRuntimeError("MCP tools response is invalid.")
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        await self.initialize()
        return await self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        self._request_id += 1
        response = await self._client.post(
            self.endpoint,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params,
            },
        )
        response.raise_for_status()
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        payload = self._response_payload(response)
        if payload.get("error"):
            raise AdvancedRuntimeError("MCP server returned an error.")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise AdvancedRuntimeError("MCP response result is invalid.")
        return result

    async def _notification(self, method: str) -> None:
        response = await self._client.post(
            self.endpoint,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": method},
        )
        response.raise_for_status()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            data_lines = [
                line[5:].strip()
                for line in response.text.splitlines()
                if line.startswith("data:")
            ]
            if not data_lines:
                raise AdvancedRuntimeError("MCP event stream was empty.")
            payload = json.loads(data_lines[-1])
        else:
            payload = response.json()
        if not isinstance(payload, dict):
            raise AdvancedRuntimeError("MCP response must be an object.")
        return payload


class AdvancedRuntimeService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        manager: ProviderManager | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.manager = manager or provider_manager
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
        self.workspace = WorkspaceRuntime(self.settings.workspace_root)
        self.rag: RagRuntime | None = None
        self.rag_provider: str | None = None
        self.rag_model: str | None = None
        self.rag_chunks = 0
        self.mcp_runtime: McpRuntime | None = None
        self.mcp_transport: McpHttpTransport | None = None
        self.mcp_tools = ToolManager()
        self.mcp_endpoint: str | None = None
        self.orchestration_runs: dict[UUID, dict[str, Any]] = {}
        self._orchestration_tasks: dict[UUID, asyncio.Task[None]] = {}
        self.scheduler_results: dict[str, dict[str, Any]] = {}
        self.scheduler = SchedulerRuntime(
            {"chat.prompt": self._scheduled_chat},
            enabled=False,
        )
        self._scheduler_state = self.settings.data_root / "scheduler_state.json"
        self._scheduler_task: asyncio.Task[None] | None = None
        self._scheduler_loaded = False

    def status(self) -> dict[str, Any]:
        return {
            "rag": {
                "enabled": bool(self.rag and self.rag.enabled),
                "configured": self.rag is not None,
                "provider": self.rag_provider,
                "model": self.rag_model,
                "chunks": self.rag_chunks,
            },
            "mcp": {
                "connected": self.mcp_runtime is not None,
                "endpoint": self.mcp_endpoint,
                "tools": self.mcp_tools.names(),
            },
            "orchestration": {
                "enabled": True,
                "runs": len(self.orchestration_runs),
                "active": sum(
                    1
                    for run in self.orchestration_runs.values()
                    if run["status"] in {"pending", "running"}
                ),
            },
            "scheduler": {
                "enabled": self.scheduler.enabled,
                "approved_actions": ["chat.prompt"],
            },
        }

    def configure_rag(
        self,
        *,
        enabled: bool,
        provider: str,
        model: str,
    ) -> dict[str, Any]:
        if not enabled:
            if self.rag:
                self.rag.enabled = False
            return self.status()["rag"]
        instance = self.manager.provider(provider)
        if not instance.local:
            raise AdvancedRuntimeError("P26 RAG accepts local providers only.")
        if not instance.supports_embeddings:
            raise AdvancedRuntimeError("Selected provider cannot create embeddings.")
        embedder = ProviderEmbeddingBackend(self.manager, provider, model)
        self.rag = RagRuntime(
            WorkspaceTextLoader(self.workspace),
            embedder,
            enabled=True,
        )
        self.rag_provider = provider
        self.rag_model = model
        self.rag_chunks = 0
        return self.status()["rag"]

    async def ingest_rag(self, path: str, *, consent: bool) -> dict[str, Any]:
        if not self.rag:
            raise AdvancedRuntimeError("Configure RAG before ingestion.")
        added = await self.rag.ingest(path, consent=consent)
        self.rag_chunks += added
        return {"added": added, "chunks": self.rag_chunks}

    async def search_rag(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        if not self.rag:
            raise AdvancedRuntimeError("Configure RAG before search.")
        return [
            result.model_dump(mode="json")
            for result in await self.rag.search(query, limit=limit)
        ]

    async def connect_mcp(
        self,
        *,
        server_id: str,
        endpoint: str,
        consent: bool,
    ) -> list[dict[str, Any]]:
        if not consent:
            raise AdvancedRuntimeError("Explicit MCP connection consent is required.")
        await self.disconnect_mcp()
        transport = McpHttpTransport(endpoint)
        runtime = McpRuntime(
            server_id=server_id,
            transport=transport,
            allowed_servers={server_id},
        )
        try:
            definitions = await runtime.discover()
        except Exception:
            await transport.close()
            raise
        manager = ToolManager()
        for definition in definitions:
            manager.register(McpTool(runtime, definition), profiles=("mcp",))
        self.mcp_transport = transport
        self.mcp_runtime = runtime
        self.mcp_tools = manager
        self.mcp_endpoint = endpoint
        return definitions

    async def invoke_mcp(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.mcp_runtime:
            raise AdvancedRuntimeError("Connect an approved MCP server first.")
        return await self.mcp_tools.execute(name, arguments)

    async def disconnect_mcp(self) -> None:
        if self.mcp_runtime:
            await self.mcp_runtime.close()
        self.mcp_runtime = None
        self.mcp_transport = None
        self.mcp_tools = ToolManager()
        self.mcp_endpoint = None

    def start_orchestration(
        self,
        *,
        provider: str,
        model: str,
        task: str,
        iterations: int,
        cost_units: int,
    ) -> dict[str, Any]:
        instance = self.manager.provider(provider)
        if not instance.local:
            raise AdvancedRuntimeError("P26 orchestration accepts local providers only.")
        run_id = uuid4()
        record: dict[str, Any] = {
            "id": str(run_id),
            "provider": provider,
            "model": model,
            "task": task,
            "status": "pending",
            "output": None,
            "error": None,
        }
        self.orchestration_runs[run_id] = record
        self._orchestration_tasks[run_id] = asyncio.create_task(
            self._execute_orchestration(
                run_id,
                provider=provider,
                model=model,
                task=task,
                iterations=iterations,
                cost_units=cost_units,
            ),
        )
        return dict(record)

    def list_orchestration(self) -> list[dict[str, Any]]:
        return [
            dict(self.orchestration_runs[key])
            for key in sorted(self.orchestration_runs, key=str)
        ]

    def cancel_orchestration(self, run_id: UUID) -> bool:
        task = self._orchestration_tasks.get(run_id)
        if not task or task.done():
            return False
        task.cancel()
        self.orchestration_runs[run_id]["status"] = "cancelled"
        return True

    async def _execute_orchestration(
        self,
        run_id: UUID,
        *,
        provider: str,
        model: str,
        task: str,
        iterations: int,
        cost_units: int,
    ) -> None:
        record = self.orchestration_runs[run_id]
        record["status"] = "running"

        async def executor(
            context: AgentContext,
            delegated_task: str,
            cancelled: asyncio.Event,
        ) -> ExecutionReport:
            if cancelled.is_set():
                return ExecutionReport(
                    output=None,
                    iterations_used=0,
                    cost_units_used=0,
                )
            raw = await self.manager.chat(
                provider=provider,
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are the {context.role} agent.",
                    },
                    {"role": "user", "content": delegated_task},
                ],
                options={"num_predict": 256, "temperature": 0.2},
                think=False,
            )
            usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
            used = int(usage.get("completion_tokens", 0) or 0)
            return ExecutionReport(
                output=str(raw.get("content", "")),
                iterations_used=1,
                cost_units_used=used,
            )

        runtime = MultiAgentRuntime(
            [
                AgentRole(name="coordinator", capabilities=frozenset({"chat"})),
                AgentRole(name="analyst", capabilities=frozenset({"chat"})),
                AgentRole(name="reviewer", capabilities=frozenset({"chat"})),
            ],
            executor,
            enabled=True,
            max_depth=1,
            max_concurrency=2,
        )
        try:
            budget = DelegationBudget(
                iterations=iterations,
                cost_units=cost_units,
            )
            root = runtime.create_root(
                "coordinator",
                permissions=frozenset({"chat"}),
                budget=budget,
            )
            child_budget = DelegationBudget(
                iterations=1,
                cost_units=max(1, cost_units // 2),
            )
            analysis = await runtime.delegate(
                root,
                DelegationRequest(
                    target_role="analyst",
                    task=task,
                    permissions=frozenset({"chat"}),
                    budget=child_budget,
                ),
            )
            review = await runtime.delegate(
                root,
                DelegationRequest(
                    target_role="reviewer",
                    task=(
                        "Review this task and analysis, then provide a final answer.\n"
                        f"Task: {task}\nAnalysis: {analysis.output}"
                    ),
                    permissions=frozenset({"chat"}),
                    budget=child_budget,
                ),
            )
            record["status"] = "completed"
            record["output"] = {
                "analysis": analysis.output,
                "review": review.output,
            }
        except asyncio.CancelledError:
            record["status"] = "cancelled"
        except Exception as exc:  # noqa: BLE001 - product boundary records failure
            record["status"] = "failed"
            record["error"] = str(exc)
        finally:
            self._orchestration_tasks.pop(run_id, None)

    async def set_scheduler_enabled(self, enabled: bool) -> dict[str, Any]:
        self.scheduler.enabled = enabled
        if enabled:
            self._load_scheduler()
            if not self._scheduler_task or self._scheduler_task.done():
                self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        elif self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None
        if enabled:
            self._save_scheduler()
        return self.scheduler_state()

    def schedule_chat(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
        run_at: datetime,
        consent: bool,
    ) -> dict[str, Any]:
        instance = self.manager.provider(provider)
        if not instance.local:
            raise AdvancedRuntimeError("P26 scheduler accepts local providers only.")
        result_id = str(uuid4())
        job = self.scheduler.schedule(
            action="chat.prompt",
            arguments={
                "provider": provider,
                "model": model,
                "prompt": prompt,
                "result_id": result_id,
            },
            run_at=run_at,
            consent=consent,
        )
        self.scheduler_results[result_id] = {"status": "pending", "content": None}
        self._save_scheduler()
        return job.model_dump(mode="json")

    def scheduler_state(self) -> dict[str, Any]:
        state = self.scheduler.export_state() if self.scheduler.enabled else {
            "jobs": [],
            "audit": [],
        }
        public_results = {
            str(job["id"]): self.scheduler_results.get(
                str(job.get("arguments", {}).get("result_id", "")),
                {"status": "pending", "content": None},
            )
            for job in state["jobs"]
        }
        return {
            "enabled": self.scheduler.enabled,
            **state,
            "results": public_results,
        }

    def cancel_scheduled(self, job_id: UUID) -> bool:
        cancelled = self.scheduler.cancel(job_id)
        if cancelled:
            self._save_scheduler()
        return cancelled

    async def run_scheduler_due(self) -> list[str]:
        completed = await self.scheduler.run_due()
        if completed:
            self._save_scheduler()
        return [str(item) for item in completed]

    async def _scheduled_chat(self, arguments: dict[str, Any]) -> dict[str, Any]:
        provider = str(arguments.get("provider", ""))
        model = str(arguments.get("model", ""))
        prompt = str(arguments.get("prompt", ""))
        result_id = str(arguments.get("result_id", ""))
        instance = self.manager.provider(provider)
        if not instance.local:
            raise AdvancedRuntimeError("Scheduled cloud calls are not enabled in P26.")
        raw = await self.manager.chat(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 256, "temperature": 0.3},
            think=False,
        )
        result = {
            "status": "completed",
            "content": str(raw.get("content", "")),
            "provider": str(raw.get("provider", provider)),
            "model": str(raw.get("model", model)),
        }
        self.scheduler_results[result_id] = result
        return result

    async def _scheduler_loop(self) -> None:
        try:
            while self.scheduler.enabled:
                await self.run_scheduler_due()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return

    def _load_scheduler(self) -> None:
        if self._scheduler_loaded or not self._scheduler_state.is_file():
            self._scheduler_loaded = True
            return
        payload = json.loads(self._scheduler_state.read_text(encoding="utf-8"))
        self.scheduler.import_state(payload.get("runtime", {}))
        results = payload.get("results", {})
        if isinstance(results, dict):
            self.scheduler_results = results
        self._scheduler_loaded = True

    def _save_scheduler(self) -> None:
        if not self._scheduler_loaded and not self.scheduler.enabled:
            return
        self._scheduler_state.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "runtime": self.scheduler.export_state() if self.scheduler.enabled else {
                "jobs": [],
                "audit": [],
            },
            "results": self.scheduler_results,
        }
        temporary = self._scheduler_state.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self._scheduler_state)

    async def close(self) -> None:
        await self.disconnect_mcp()
        for task in tuple(self._orchestration_tasks.values()):
            task.cancel()
        if self._orchestration_tasks:
            await asyncio.gather(
                *self._orchestration_tasks.values(),
                return_exceptions=True,
            )
        if self._scheduler_task:
            self._scheduler_task.cancel()
            await asyncio.gather(self._scheduler_task, return_exceptions=True)
            self._scheduler_task = None


advanced_runtime_service = AdvancedRuntimeService()
