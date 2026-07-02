"""
End-to-end walk-through against the retrieval core (in-process, no server needed).
Shows: ingest -> retrieve -> answer -> tenant isolation -> GDPR erasure.

    python demo.py
"""
from fastapi.testclient import TestClient

from app.retrieval_api import app

c = TestClient(app)

DOCS = {
    "gex44": "Der Hetzner GEX44 ist ein dedizierter GPU-Server mit einer Grafikkarte der Ada-Generation und viel VRAM.",
    "qdrant": "Qdrant ist eine Vektordatenbank. Pro Mandant wird eine eigene Collection angelegt, was Isolation und Loeschung erleichtert.",
    "ollama": "Ollama fuehrt lokale Sprachmodelle wie Qwen3 14B aus. Es werden keine externen APIs aufgerufen.",
}

print("== ingest (tenant: acme) ==")
for did, text in DOCS.items():
    print(" ", c.post("/v1/ingest", json={"tenant": "acme", "doc_id": did, "text": text}).json())

print("\n== retrieve: 'Wie funktioniert die Vektordatenbank?' ==")
r = c.post("/v1/retrieve", json={"tenant": "acme", "query": "Wie funktioniert die Vektordatenbank?", "top_k": 2})
for hit in r.json()["results"]:
    print(f"  {hit['id']:8s} score={hit['score']:.3f}")

print("\n== answer ==")
a = c.post("/v1/answer", json={"tenant": "acme", "query": "Was macht Ollama?", "top_k": 2}).json()
print("  answer :", a["answer"])
print("  sources:", a["sources"])

print("\n== tenant isolation (tenant 'stranger' sees nothing) ==")
print("  ", c.post("/v1/retrieve", json={"tenant": "stranger", "query": "Ollama", "top_k": 2}).json()["results"])

print("\n== GDPR erasure of tenant 'acme' ==")
print("  ", c.delete("/v1/tenant/acme").json())
print("  after erase:", c.post("/v1/retrieve", json={"tenant": "acme", "query": "Ollama", "top_k": 2}).json()["results"])
