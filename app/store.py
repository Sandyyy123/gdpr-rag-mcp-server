"""
Per-tenant vector store.

Uses Qdrant when QDRANT_URL is set and the client is reachable; otherwise falls
back to a dependency-free in-memory store so the repo runs anywhere for a demo.
Tenant isolation is modelled the way the production build does it: one collection
per tenant, so isolation and GDPR erasure happen at the collection boundary.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Dict, List, Tuple


def _collection_name(tenant_id: str) -> str:
    # one collection per tenant -> hard isolation + clean per-tenant deletion
    return f"tenant_{tenant_id}"


class InMemoryStore:
    """Cosine-similarity store, one bucket per tenant collection."""

    def __init__(self) -> None:
        self._data: Dict[str, List[Tuple[str, List[float], dict]]] = defaultdict(list)

    def upsert(self, tenant_id: str, doc_id: str, vector: List[float], payload: dict) -> None:
        self._data[_collection_name(tenant_id)].append((doc_id, vector, payload))

    def search(self, tenant_id: str, vector: List[float], top_k: int) -> List[dict]:
        rows = self._data.get(_collection_name(tenant_id), [])
        scored = [
            {"id": did, "score": _cosine(vector, vec), "payload": pl}
            for did, vec, pl in rows
        ]
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]

    def drop_tenant(self, tenant_id: str) -> bool:
        """GDPR right-to-erasure: drop the whole tenant collection."""
        return self._data.pop(_collection_name(tenant_id), None) is not None

    def tenants(self) -> List[str]:
        return [k.replace("tenant_", "", 1) for k in self._data]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def get_store():
    """Return a Qdrant-backed store if configured and importable, else in-memory."""
    url = os.getenv("QDRANT_URL")
    if not url:
        return InMemoryStore()
    try:
        from qdrant_client import QdrantClient  # noqa: F401

        return QdrantStore(url)
    except Exception:
        # qdrant not installed / not reachable -> demo fallback
        return InMemoryStore()


class QdrantStore:
    """Thin Qdrant adapter with the same interface as InMemoryStore."""

    def __init__(self, url: str) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm

        self._qm = qm
        self.client = QdrantClient(url=url)

    def _ensure(self, tenant_id: str, dim: int) -> None:
        name = _collection_name(tenant_id)
        existing = {c.name for c in self.client.get_collections().collections}
        if name not in existing:
            self.client.create_collection(
                collection_name=name,
                vectors_config=self._qm.VectorParams(
                    size=dim, distance=self._qm.Distance.COSINE
                ),
            )

    def upsert(self, tenant_id: str, doc_id: str, vector: List[float], payload: dict) -> None:
        self._ensure(tenant_id, len(vector))
        self.client.upsert(
            collection_name=_collection_name(tenant_id),
            points=[self._qm.PointStruct(id=abs(hash(doc_id)) % (10**12),
                                         vector=vector, payload={**payload, "doc_id": doc_id})],
        )

    def search(self, tenant_id: str, vector: List[float], top_k: int) -> List[dict]:
        hits = self.client.search(
            collection_name=_collection_name(tenant_id), query_vector=vector, limit=top_k
        )
        return [{"id": h.payload.get("doc_id"), "score": h.score, "payload": h.payload} for h in hits]

    def drop_tenant(self, tenant_id: str) -> bool:
        self.client.delete_collection(collection_name=_collection_name(tenant_id))
        return True

    def tenants(self) -> List[str]:
        return [c.name.replace("tenant_", "", 1)
                for c in self.client.get_collections().collections
                if c.name.startswith("tenant_")]
