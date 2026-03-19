"""Optional embedding-based semantic routing for skill retrieval.

Falls back gracefully to zero scores if sentence-transformers is not installed,
preserving the zero-dependency contract of agent_swarm core.

Install: pip install agent-swarm-core[semantic]
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("agent_swarm")

# ---------------------------------------------------------------------------
# Lazy numpy import (also optional, comes with sentence-transformers)
# ---------------------------------------------------------------------------
_np = None


def _get_np():
    global _np
    if _np is None:
        try:
            import numpy as np
            _np = np
        except ImportError:
            pass
    return _np


class SemanticRouter:
    """Optional embedding-based skill routing.

    * Lazy-loads sentence-transformers on first ``encode()`` call.
    * Caches embeddings keyed by text to avoid redundant computation.
    * If the library is missing, all public methods return safe defaults
      so the caller never needs to guard with ``if available()``.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = None
        self._model_name = model_name
        self._cache: Dict[str, object] = {}  # text → ndarray
        self._available: Optional[bool] = None  # tri-state: None = unchecked

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Return True if sentence-transformers can be imported."""
        if self._available is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
                logger.debug("sentence-transformers not installed — semantic routing disabled")
        return self._available

    def encode(self, text: str) -> Optional[object]:
        """Encode *text* to an embedding vector. Returns ``None`` if unavailable."""
        if not self.available():
            return None
        if text in self._cache:
            return self._cache[text]
        model = self._load_model()
        if model is None:
            return None
        vec = model.encode(text, normalize_embeddings=True)
        self._cache[text] = vec
        return vec

    def score(self, query: str, documents: List[str]) -> List[float]:
        """Cosine similarity between *query* and each document.

        Returns a list of ``0.0`` values when the library is unavailable,
        so callers can unconditionally add the result.
        """
        np = _get_np()
        if not self.available() or np is None:
            return [0.0] * len(documents)

        q_vec = self.encode(query)
        if q_vec is None:
            return [0.0] * len(documents)

        scores: List[float] = []
        for doc in documents:
            d_vec = self.encode(doc)
            if d_vec is None:
                scores.append(0.0)
            else:
                # Vectors are already L2-normalized, so dot == cosine similarity
                sim = float(np.dot(q_vec, d_vec))
                scores.append(max(0.0, sim))  # clamp negatives
        return scores

    def invalidate(self, text: str) -> None:
        """Remove a cached embedding (e.g. when a skill principle changes)."""
        self._cache.pop(text, None)

    def invalidate_all(self) -> None:
        """Clear the entire embedding cache."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            logger.info("Loaded semantic model: %s", self._model_name)
            return self._model
        except Exception as exc:
            logger.warning("Failed to load semantic model: %s", exc)
            self._available = False
            return None
