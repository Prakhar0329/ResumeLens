"""Sentence embeddings with sentence-transformers (CPU only).

The model is loaded once at startup (see ``app.main`` lifespan) and shared across
requests. ``EmbeddingCache`` de-duplicates texts within one request so each unique
string is encoded exactly once, in a single batched call.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

import numpy as np

logger = logging.getLogger("resumelens.embedder")


class EmbedderProtocol(Protocol):
    model_name: str

    @property
    def loaded(self) -> bool: ...

    def load(self) -> None: ...

    def encode(self, texts: list[str]) -> np.ndarray: ...


class Embedder:
    def __init__(self, model_name: str, batch_size: int = 32, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        self._model = None
        self._dim: int | None = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            # Imported lazily: torch is heavy and not needed to import the app.
            from sentence_transformers import SentenceTransformer

            start = time.perf_counter()
            self._model = SentenceTransformer(self.model_name, device="cpu", cache_folder=self.cache_dir)
            self._dim = int(self._model.get_sentence_embedding_dimension())
            logger.info(
                "embedding_model_loaded",
                extra={
                    "fields": {
                        "model": self.model_name,
                        "dim": self._dim,
                        "seconds": round(time.perf_counter() - start, 2),
                    }
                },
            )

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts into L2-normalised float32 vectors of shape (n, dim)."""
        self.load()
        assert self._model is not None and self._dim is not None
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


class EmbeddingCache:
    """Per-request cache: encodes each distinct text once."""

    def __init__(self, embedder: EmbedderProtocol) -> None:
        self.embedder = embedder
        self._vectors: dict[str, np.ndarray] = {}

    def encode(self, texts: list[str]) -> np.ndarray:
        missing = list(dict.fromkeys(t for t in texts if t not in self._vectors))
        if missing:
            vectors = self.embedder.encode(missing)
            for text, vec in zip(missing, vectors, strict=False):
                self._vectors[text] = vec
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        return np.vstack([self._vectors[t] for t in texts])


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between rows of ``a`` and rows of ``b`` (inputs are normalised)."""
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0] if b.ndim == 2 else 0), dtype=np.float32)
    return np.clip(a @ b.T, -1.0, 1.0)
