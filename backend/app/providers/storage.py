import asyncio
import json
from pathlib import Path
from typing import Any

from app.providers.models import ProviderConfig


class ProviderStorageError(RuntimeError):
    """Raised when provider storage cannot be read or written."""


class ProviderStorage:
    """JSON-backed provider configuration storage."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._lock = asyncio.Lock()

    @property
    def file_path(self) -> Path:
        return self._file_path

    async def initialize(self) -> None:
        """Create the storage directory and file when missing."""

        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self._file_path.exists():
            self._write_json_sync(
                {
                    "version": 1,
                    "providers": [],
                },
            )

    async def list_all(self) -> list[ProviderConfig]:
        """Load all provider configurations."""

        async with self._lock:
            return await asyncio.to_thread(self._list_all_sync)

    def _list_all_sync(self) -> list[ProviderConfig]:
        self._initialize_sync()

        raw_data = self._read_json_sync()
        providers = raw_data.get("providers", [])

        if not isinstance(providers, list):
            raise ProviderStorageError(
                "The providers storage format is invalid.",
            )

        try:
            return [ProviderConfig.model_validate(item) for item in providers]
        except Exception as exc:
            raise ProviderStorageError(
                "Provider configuration validation failed.",
            ) from exc

    async def replace_all(
        self,
        providers: list[ProviderConfig],
    ) -> None:
        """Replace all stored provider configurations."""

        async with self._lock:
            await asyncio.to_thread(
                self._replace_all_sync,
                providers,
            )

    def _replace_all_sync(
        self,
        providers: list[ProviderConfig],
    ) -> None:
        self._initialize_sync()

        payload = {
            "version": 1,
            "providers": [
                provider.model_dump(
                    mode="json",
                    exclude_none=False,
                )
                for provider in providers
            ],
        }

        self._write_json_sync(payload)

    def _read_json_sync(self) -> dict[str, Any]:
        try:
            content = self._file_path.read_text(
                encoding="utf-8-sig",
            )

            if not content.strip():
                return {
                    "version": 1,
                    "providers": [],
                }

            data = json.loads(content)

            if not isinstance(data, dict):
                raise ProviderStorageError(
                    "Provider storage root must be an object.",
                )

            return data

        except json.JSONDecodeError as exc:
            raise ProviderStorageError(
                f"Invalid JSON in {self._file_path}.",
            ) from exc

        except OSError as exc:
            raise ProviderStorageError(
                f"Unable to read {self._file_path}.",
            ) from exc

    def _write_json_sync(
        self,
        payload: dict[str, Any],
    ) -> None:
        temporary_path = self._file_path.with_suffix(
            f"{self._file_path.suffix}.tmp",
        )

        try:
            serialized = json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )

            temporary_path.write_text(
                serialized + "\n",
                encoding="utf-8",
            )

            temporary_path.replace(self._file_path)

        except OSError as exc:
            raise ProviderStorageError(
                f"Unable to write {self._file_path}.",
            ) from exc

        finally:
            if temporary_path.exists():
                temporary_path.unlink(missing_ok=True)
