"""
End-to-end tests against the retrieval core using FastAPI's TestClient.
Runs with the in-memory + fallback backends, so no Qdrant/Ollama needed in CI.
"""
from fastapi.testclient import TestClient

from app.retrieval_api import app

client = TestClient(app)

DOCS = {
    "d1": "Der GEX44 ist ein GPU-Server von Hetzner mit einer Grafikkarte der Ada-Generation.",
    "d2": "Qdrant speichert Vektoren; pro Mandant wird eine eigene Collection angelegt.",
    "d3": "Ollama fuehrt lokale Sprachmodelle wie Qwen3 aus, ohne externe API-Aufrufe.",
}


def _seed(tenant="acme"):
    for did, text in DOCS.items():
        r = client.post("/v1/ingest", json={"tenant": tenant, "doc_id": did, "text": text})
        assert r.status_code == 200


def test_health():
    assert client.get("/healthz").json()["status"] == "ok"


def test_retrieve_ranks_relevant_doc_first():
    _seed()
    r = client.post("/v1/retrieve", json={"tenant": "acme", "query": "Was ist Qdrant?", "top_k": 3})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, "expected at least one hit"
    assert results[0]["id"] == "d2"


def test_tenant_isolation():
    _seed("acme")
    # a different tenant sees nothing from acme
    r = client.post("/v1/retrieve", json={"tenant": "other", "query": "Qdrant", "top_k": 3})
    assert r.json()["results"] == []


def test_answer_returns_sources():
    _seed()
    r = client.post("/v1/answer", json={"tenant": "acme", "query": "Was macht Ollama?", "top_k": 2})
    body = r.json()
    assert "answer" in body and body["sources"]


def test_gdpr_erasure_drops_tenant():
    _seed("wipe-me")
    assert client.delete("/v1/tenant/wipe-me").json()["erased"] is True
    assert client.post("/v1/retrieve",
                       json={"tenant": "wipe-me", "query": "x", "top_k": 3}).json()["results"] == []
