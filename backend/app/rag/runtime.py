from __future__ import annotations

import math

from app.rag.chunker import DeterministicChunker
from app.rag.embedding import EmbeddingBackend
from app.rag.loader import WorkspaceTextLoader
from app.rag.models import RagChunk, RagCitation, RagResult


class RagDisabledError(RuntimeError):
    pass


class RagConsentRequiredError(RuntimeError):
    pass


class RagRuntime:
    def __init__(self, loader: WorkspaceTextLoader, embedder: EmbeddingBackend, *, enabled: bool = False) -> None:
        self._loader = loader
        self._embedder = embedder
        self._chunker = DeterministicChunker()
        self.enabled = enabled
        self._index: list[tuple[RagChunk, list[float]]] = []

    async def ingest(self, path: str, *, consent: bool, cloud_consent: bool = False) -> int:
        self._require_enabled_and_consent(consent)
        chunks = self._chunker.chunk(self._loader.load(path))
        vectors = await self._embedder.embed([chunk.text for chunk in chunks], cloud_consent=cloud_consent)
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding count does not match chunk count.")
        self._index.extend(zip(chunks, vectors, strict=True))
        return len(chunks)

    async def search(self, query: str, *, limit: int = 5, cloud_consent: bool = False) -> list[RagResult]:
        self._require_enabled()
        if limit < 1:
            raise ValueError("limit must be positive.")
        vectors = await self._embedder.embed([query], cloud_consent=cloud_consent)
        if len(vectors) != 1:
            raise RuntimeError("Query embedding is invalid.")
        scored = sorted(
            ((self._cosine(vectors[0], vector), chunk) for chunk, vector in self._index),
            key=lambda item: (-item[0], item[1].source, item[1].start),
        )[:limit]
        return [RagResult(
            text=chunk.text, score=score,
            citation=RagCitation(source=chunk.source, start=chunk.start, end=chunk.end),
            untrusted_instructions=chunk.untrusted_instructions,
        ) for score, chunk in scored]

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RagDisabledError("RAG is disabled.")

    def _require_enabled_and_consent(self, consent: bool) -> None:
        self._require_enabled()
        if not consent:
            raise RagConsentRequiredError("Explicit ingestion consent is required.")

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            raise ValueError("Embedding dimensions must be equal and non-empty.")
        denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
        return 0.0 if denominator == 0 else sum(x * y for x, y in zip(left, right, strict=True)) / denominator
