"""
Embedding provider.

Prefers a real local sentence-transformers model (no external API -> GDPR-safe);
falls back to a deterministic hashing embedding so the demo runs with zero heavy
deps. The public function is identical either way, so the retrieval API never
needs to know which backend is active.
"""
from __future__ import annotations

import hashlib
import os
from typing import List

_DIM = 256
_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    if os.getenv("USE_ST", "1") == "1":
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(
                os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            )
            return _model
        except Exception:
            _model = False  # mark: unavailable, use fallback
    else:
        _model = False
    return _model


def embed(text: str) -> List[float]:
    m = _load_model()
    if m:
        return m.encode(text, normalize_embeddings=True).tolist()
    return _hash_embed(text)


def _hash_embed(text: str) -> List[float]:
    """Deterministic bag-of-tokens hashing embedding (demo fallback)."""
    vec = [0.0] * _DIM
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % _DIM] += 1.0
    return vec


def _tokenize(text: str) -> List[str]:
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if t]
