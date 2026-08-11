from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.services.cloud_provider_service import (
    CloudProviderService,
    CloudTrainingConnection,
    cloud_provider_service,
)
from app.training.local_lora import (
    LocalRunner,
    LocalTrainingCancelled,
    TransformersLoraRunner,
    valid_loss,
)
from app.training.models import (
    LocalTrainingCapability,
    TrainingCapabilities,
    TrainingJob,
    TrainingJobCreate,
    TrainingMessage,
    TrainingMetric,
    TrainingModel,
)


class TrainingError(RuntimeError):
    pass


_ACTIVE = {"validating", "uploading", "queued", "running", "unknown"}
_STATUS = {
    "validating_files": "validating",
    "queued": "queued",
    "running": "running",
    "succeeded": "succeeded",
    "failed": "failed",
    "cancelled": "cancelled",
}
_MAX_DATASET_BYTES = 512_000
_MAX_JOBS = 50
_MAX_ACTIVE_JOBS = 2
_MAX_METRICS = 200
_MAX_LOCAL_MODELS = 50
_TOKENIZER_FILES = {"tokenizer.json", "tokenizer_config.json", "tokenizer.model", "spiece.model"}


class TrainingService:
    """Normalizes cloud fine-tuning and bounded local LoRA jobs."""

    def __init__(
        self,
        *,
        cloud: CloudProviderService | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        local_runner: LocalRunner | None = None,
        model_root: Path | None = None,
        output_root: Path | None = None,
    ) -> None:
        settings = get_settings()
        self.cloud = cloud or cloud_provider_service
        self.transport = transport
        self.local_runner = local_runner or TransformersLoraRunner()
        self.model_root = (model_root or settings.training_model_root).resolve()
        self.output_root = (output_root or settings.training_output_root).resolve()
        self._jobs: dict[UUID, TrainingJob] = {}
        self._cancellations: dict[UUID, Event] = {}
        self._threads: dict[UUID, Thread] = {}
        self._lock = RLock()

    async def capabilities(self) -> TrainingCapabilities:
        cloud_models = [TrainingModel(**item) for item in await self.cloud.training_model_items()]
        local_models = self._local_models()
        missing = self.local_runner.missing_packages()
        if missing:
            local = LocalTrainingCapability(
                available=False,
                reason=(
                    "請從 Linlin-Agent.bat 安裝本機 LoRA 訓練支援："
                    f"尚缺 {', '.join(missing)}。"
                ),
            )
        elif not local_models:
            local = LocalTrainingCapability(
                available=False,
                reason=(
                    "尚未註冊可訓練的 Hugging Face 權重；請將包含 config、"
                    "tokenizer 與權重檔的模型目錄放進 models/。"
                ),
            )
        else:
            local = LocalTrainingCapability(
                available=True,
                reason=f"已找到 {len(local_models)} 個可用的本機 LoRA 模型。",
            )
        return TrainingCapabilities(models=local_models + cloud_models, local=local)

    async def create(self, payload: TrainingJobCreate) -> TrainingJob:
        if self._active_count() >= _MAX_ACTIVE_JOBS:
            raise TrainingError("At most two training jobs may be active at once.")
        if payload.engine == "local_lora":
            return self._create_local(payload)
        return await self._create_cloud(payload)

    async def _create_cloud(self, payload: TrainingJobCreate) -> TrainingJob:
        if not payload.cloud_consent:
            raise TrainingError("Explicit cloud training-data consent is required.")
        connection = await self.cloud.training_connection(payload.provider)
        dataset, examples = self._dataset(payload)
        now = datetime.now(UTC)
        local_id = uuid4()
        file_id: str | None = None
        async with self._client(connection) as client:
            try:
                uploaded = await self._request(
                    client,
                    "POST",
                    "files",
                    data={"purpose": "fine-tune"},
                    files={"file": ("linlin-conversation.jsonl", dataset, "application/jsonl")},
                )
                file_id = self._required_string(uploaded, "id", "training file")
                created = await self._request(
                    client,
                    "POST",
                    "fine_tuning/jobs",
                    json={"training_file": file_id, "model": payload.model},
                )
            except Exception:
                if file_id:
                    try:
                        await self._request(client, "DELETE", f"files/{file_id}")
                    except TrainingError:
                        pass
                raise

        job = TrainingJob(
            id=local_id,
            conversation_id=payload.conversation_id,
            engine="openai_compatible",
            provider=payload.provider,
            provider_label=connection.label,
            model=payload.model,
            provider_job_id=self._required_string(created, "id", "training job"),
            status=self._status(created),
            examples=examples,
            created_at=now,
            updated_at=now,
            trained_model=self._optional_string(created.get("fine_tuned_model")),
            error=self._provider_error(created),
        )
        with self._lock:
            self._jobs[local_id] = job
            self._trim()
        return job.model_copy(deep=True)

    def _create_local(self, payload: TrainingJobCreate) -> TrainingJob:
        if not payload.local_consent:
            raise TrainingError("Explicit local training and resource-use consent is required.")
        if payload.provider != "local:lora":
            raise TrainingError("Local LoRA jobs require the registered local training provider.")
        missing = self.local_runner.missing_packages()
        if missing:
            raise TrainingError(f"Local training dependencies are missing: {', '.join(missing)}.")
        model_path = self._registered_model(payload.model)
        _, examples = self._dataset(payload)
        local_id = uuid4()
        now = datetime.now(UTC)
        job = TrainingJob(
            id=local_id,
            conversation_id=payload.conversation_id,
            engine="local_lora",
            provider="local:lora",
            provider_label="本機 LoRA",
            model=payload.model,
            provider_job_id=f"local-{local_id}",
            status="queued",
            examples=examples,
            created_at=now,
            updated_at=now,
        )
        cancellation = Event()
        output_path = self._job_output(local_id)
        thread = Thread(
            target=self._run_local,
            kwargs={
                "job": job,
                "model_path": model_path,
                "output_path": output_path,
                "messages": payload.messages,
                "max_steps": payload.max_steps,
                "cancelled": cancellation,
            },
            name=f"linlin-local-training-{local_id}",
            daemon=True,
        )
        with self._lock:
            self._jobs[local_id] = job
            self._cancellations[local_id] = cancellation
            self._threads[local_id] = thread
            self._trim()
        thread.start()
        return job.model_copy(deep=True)

    def _run_local(
        self,
        *,
        job: TrainingJob,
        model_path: Path,
        output_path: Path,
        messages: list[TrainingMessage],
        max_steps: int,
        cancelled: Event,
    ) -> None:
        try:
            self._set_local_state(job, "running")
            self.local_runner.run(
                model_path=model_path,
                output_path=output_path,
                messages=messages,
                max_steps=max_steps,
                cancelled=cancelled,
                progress=lambda step, loss: self._local_progress(job, step, loss),
            )
            if cancelled.is_set():
                self._set_local_state(job, "cancelled")
            else:
                relative = (output_path / "adapter").relative_to(self.output_root)
                self._set_local_state(job, "succeeded", trained_model=relative.as_posix())
        except LocalTrainingCancelled:
            self._set_local_state(job, "cancelled")
        except Exception as exc:  # noqa: BLE001 - background ML failures stay contained
            if cancelled.is_set():
                self._set_local_state(job, "cancelled")
            else:
                self._set_local_state(
                    job,
                    "failed",
                    error=f"Local LoRA training failed ({type(exc).__name__}).",
                )
        finally:
            with self._lock:
                self._cancellations.pop(job.id, None)
                self._threads.pop(job.id, None)

    async def list(self, conversation_id: str, *, refresh: bool = True) -> list[TrainingJob]:
        if len(conversation_id) > 128:
            raise TrainingError("Conversation id is too long.")
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.conversation_id == conversation_id]
        if refresh:
            for job in jobs:
                if job.engine == "openai_compatible" and job.status in _ACTIVE:
                    await self._refresh(job)
        with self._lock:
            return [
                job.model_copy(deep=True)
                for job in sorted(jobs, key=lambda item: item.created_at)
            ]

    async def cancel(self, job_id: UUID, *, conversation_id: str) -> TrainingJob:
        job = self._job(job_id, conversation_id)
        if job.status not in _ACTIVE:
            return job.model_copy(deep=True)
        if job.engine == "local_lora":
            with self._lock:
                cancellation = self._cancellations.get(job.id)
                if cancellation:
                    cancellation.set()
                job.status = "cancelled"
                job.updated_at = datetime.now(UTC)
                return job.model_copy(deep=True)
        connection = await self.cloud.training_connection(job.provider)
        async with self._client(connection) as client:
            document = await self._request(
                client,
                "POST",
                f"fine_tuning/jobs/{job.provider_job_id}/cancel",
            )
        self._update(job, document)
        return job.model_copy(deep=True)

    def _local_models(self) -> list[TrainingModel]:
        if not self.model_root.is_dir() or self.local_runner.missing_packages():
            return []
        models: list[TrainingModel] = []
        for config in sorted(self.model_root.glob("**/config.json")):
            if len(models) >= _MAX_LOCAL_MODELS:
                break
            directory = config.parent.resolve()
            try:
                relative = directory.relative_to(self.model_root)
            except ValueError:
                continue
            if len(relative.parts) > 3 or not self._has_model_files(directory):
                continue
            models.append(
                TrainingModel(
                    engine="local_lora",
                    provider="local:lora",
                    provider_label="本機 LoRA",
                    model=relative.as_posix(),
                    local=True,
                    size_bytes=self._model_size(directory),
                )
            )
        return models

    def _registered_model(self, model: str) -> Path:
        candidates = {item.model: item for item in self._local_models()}
        if model not in candidates:
            raise TrainingError("Local model is not a registered trainable weight directory.")
        path = (self.model_root / Path(model)).resolve()
        try:
            path.relative_to(self.model_root)
        except ValueError as exc:
            raise TrainingError("Local model path escapes the registered model root.") from exc
        return path

    def _job_output(self, job_id: UUID) -> Path:
        target = (self.output_root / str(job_id)).resolve()
        try:
            target.relative_to(self.output_root)
        except ValueError as exc:
            raise TrainingError("Training output path is outside the configured root.") from exc
        return target

    def _has_model_files(self, directory: Path) -> bool:
        config = self._safe_model_file(directory / "config.json")
        tokenizer = any(self._safe_model_file(directory / name) for name in _TOKENIZER_FILES)
        weights = any(self._safe_model_file(path) for path in directory.glob("*.safetensors"))
        weights = weights or self._safe_model_file(directory / "pytorch_model.bin")
        return config and tokenizer and weights

    def _safe_model_file(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            path.resolve().relative_to(self.model_root)
        except (OSError, ValueError):
            return False
        return True

    @staticmethod
    def _model_size(directory: Path) -> int:
        total = 0
        for path in directory.iterdir():
            if path.is_file() and not path.is_symlink():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
        return total

    def _active_count(self) -> int:
        with self._lock:
            return sum(job.status in _ACTIVE for job in self._jobs.values())

    def _local_progress(self, job: TrainingJob, step: int, loss: float | None) -> None:
        with self._lock:
            normalized = valid_loss(loss)
            existing = {metric.step: metric for metric in job.metrics}
            existing[step] = TrainingMetric(step=step, train_loss=normalized)
            job.metrics = [existing[key] for key in sorted(existing)][-_MAX_METRICS:]
            job.updated_at = datetime.now(UTC)

    def _set_local_state(
        self,
        job: TrainingJob,
        status: str,
        *,
        trained_model: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job.status = status  # type: ignore[assignment]
            job.trained_model = trained_model
            job.error = error
            job.updated_at = datetime.now(UTC)

    async def _refresh(self, job: TrainingJob) -> None:
        connection = await self.cloud.training_connection(job.provider)
        async with self._client(connection) as client:
            document = await self._request(client, "GET", f"fine_tuning/jobs/{job.provider_job_id}")
            self._update(job, document)
            try:
                checkpoints = await self._request(
                    client,
                    "GET",
                    f"fine_tuning/jobs/{job.provider_job_id}/checkpoints?limit={_MAX_METRICS}",
                )
            except TrainingError:
                return
        job.metrics = self._metrics(checkpoints)

    def _client(self, connection: CloudTrainingConnection) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{connection.base_url.rstrip('/')}/",
            headers={"Authorization": f"Bearer {connection.api_key}"},
            timeout=connection.timeout,
            transport=self.transport,
        )

    @staticmethod
    async def _request(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise TrainingError("Training provider connection failed.") from exc
        if response.status_code >= 400:
            raise TrainingError(f"Training provider returned HTTP {response.status_code}.")
        try:
            document = response.json()
        except ValueError as exc:
            raise TrainingError("Training provider returned invalid JSON.") from exc
        if not isinstance(document, dict):
            raise TrainingError("Training provider returned an invalid response object.")
        return document

    @staticmethod
    def _dataset(payload: TrainingJobCreate) -> tuple[bytes, int]:
        examples: list[dict[str, Any]] = []
        context: list[dict[str, str]] = []
        for message in payload.messages:
            normalized = {"role": message.role, "content": message.content.strip()}
            context.append(normalized)
            if message.role == "assistant" and any(item["role"] == "user" for item in context):
                examples.append({"messages": list(context)})
                context = [item for item in context if item["role"] == "system"]
        if not examples:
            raise TrainingError("Conversation contains no complete user/assistant training example.")
        encoded = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in examples).encode()
        if len(encoded) > _MAX_DATASET_BYTES:
            raise TrainingError("Conversation training data exceeds the 512 KB limit.")
        return encoded, len(examples)

    @staticmethod
    def _status(document: dict[str, Any]) -> str:
        raw = str(document.get("status", "queued"))
        return _STATUS.get(raw, "unknown" if raw else "queued")

    @staticmethod
    def _provider_error(document: dict[str, Any]) -> str | None:
        error = document.get("error")
        if not error:
            return None
        if isinstance(error, dict):
            code = error.get("code")
            return f"Provider training error{f' ({code})' if code else ''}."
        return "Provider training error."

    @staticmethod
    def _metrics(document: dict[str, Any]) -> list[TrainingMetric]:
        items = document.get("data", [])
        if not isinstance(items, list):
            return []
        metrics: dict[int, TrainingMetric] = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("step_number"), int):
                continue
            values = item.get("metrics", {})
            if not isinstance(values, dict):
                continue
            step = item["step_number"]
            metrics[step] = TrainingMetric(
                step=step,
                train_loss=TrainingService._number(values.get("train_loss")),
                valid_loss=TrainingService._number(values.get("valid_loss")),
            )
        return [metrics[key] for key in sorted(metrics)][-_MAX_METRICS:]

    @staticmethod
    def _number(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _required_string(document: dict[str, Any], key: str, label: str) -> str:
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise TrainingError(f"Provider did not return a {label} id.")
        return value

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _update(job: TrainingJob, document: dict[str, Any]) -> None:
        job.status = TrainingService._status(document)  # type: ignore[assignment]
        job.trained_model = TrainingService._optional_string(document.get("fine_tuned_model"))
        job.error = TrainingService._provider_error(document)
        job.updated_at = datetime.now(UTC)

    def _job(self, job_id: UUID, conversation_id: str) -> TrainingJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.conversation_id != conversation_id:
                raise TrainingError("Training job was not found for this conversation.")
            return job

    def _trim(self) -> None:
        if len(self._jobs) <= _MAX_JOBS:
            return
        terminal = sorted(
            (job for job in self._jobs.values() if job.status not in _ACTIVE),
            key=lambda item: item.updated_at,
        )
        for job in terminal[: len(self._jobs) - _MAX_JOBS]:
            self._jobs.pop(job.id, None)


training_service = TrainingService()
