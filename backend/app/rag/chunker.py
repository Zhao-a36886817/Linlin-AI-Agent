from __future__ import annotations

import hashlib
import re

from app.rag.loader import RagDocument
from app.rag.models import RagChunk

_INJECTION = re.compile(r"(?i)(ignore (?:all )?(?:previous|prior) instructions|system prompt|developer message)")


class DeterministicChunker:
    def __init__(self, chunk_size: int = 800, overlap: int = 100) -> None:
        if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("chunk_size and overlap are invalid.")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, document: RagDocument) -> list[RagChunk]:
        chunks: list[RagChunk] = []
        step = self.chunk_size - self.overlap
        for start in range(0, len(document.text), step):
            end = min(start + self.chunk_size, len(document.text))
            text = document.text[start:end]
            if not text:
                break
            digest = hashlib.sha256(f"{document.source}:{start}:{end}:{text}".encode()).hexdigest()[:16]
            chunks.append(RagChunk(
                id=digest, source=document.source, text=text, start=start, end=end,
                untrusted_instructions=bool(_INJECTION.search(text)),
            ))
            if end == len(document.text):
                break
        return chunks
