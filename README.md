> **⚠️ Proprietary — All Rights Reserved.** © 2026 Sandeep Grover. This repository is licensed to Sandeep Grover and may **not** be used, run, copied, modified, distributed, or used to train models without prior written permission. Public visibility does not grant a license. See [LICENSE](LICENSE).

---

# GDPR-Compliant RAG / MCP Knowledge Server

A **frontend-agnostic retrieval core** for a private, GDPR-compliant knowledge server that
runs entirely on a German host (e.g. Hetzner GEX44 GPU). The internal retrieval API is the
single source of truth; the **MCP server** and a **later custom UI** attach to it as
**parallel clients**, never in series.

> Demo scope: this repo is a runnable reference of the architecture. It runs with zero heavy
> deps (in-memory vector store + extractive fallback) and upgrades to the full stack
> (Qdrant + Ollama/Qwen3 + PostgreSQL) via Docker Compose - no code changes.

## Architecture

```
        MCP server            Custom UI (later)         Eval / CI client
   (Streamable HTTP + OAuth)   (same contract)        (German test set)
            \                       |                       /
             \______________________|______________________/
                                    |
                      Internal Retrieval API  (FastAPI)      <-- the ONLY core
                embed · per-tenant search · re-rank · prompt · LLM call
                        |                 |                 |
                     Qdrant            Ollama            PostgreSQL
              (per-tenant           (Qwen3 14B,        (tenants, meta,
               collections)          local only)        audit, OAuth)
```

**Why parallel, not serial:** the MCP server holds no retrieval logic. It translates MCP tool
calls into the retrieval API's HTTP contract and forwards them. The future UI calls the exact
same endpoints. You can add, swap, or remove a client without touching retrieval, and improve
retrieval once for every client at the same time.

## Endpoints (retrieval core, versioned contract)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/ingest` | Index a document chunk for a tenant |
| POST | `/v1/retrieve` | Ranked source chunks for a query |
| POST | `/v1/answer` | Grounded German answer + sources |
| DELETE | `/v1/tenant/{tenant}` | GDPR erasure - drop the tenant collection |
| GET | `/v1/tenants` | List tenants |
| GET | `/healthz` | Health |

## Run the demo locally (no GPU, no Docker)

```bash
pip install -r requirements.txt
uvicorn app.retrieval_api:app --port 8000    # terminal 1: the core
uvicorn app.mcp_server:app --port 8080       # terminal 2: MCP client
python demo.py                               # seed + query end-to-end
pytest -q                                     # test suite
```

## Run the full stack (German host)

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3:14b
```

`retrieval-api` auto-detects `QDRANT_URL` and `OLLAMA_URL` and uses the real backends; nothing
in the application code changes.

## GDPR by design

- **Data residency** - all compute and storage on the German host; no external LLM/embedding API.
- **Tenant isolation** - one Qdrant collection per tenant + tenant-scoped OAuth 2.0.
- **Right to erasure** - `DELETE /v1/tenant/{tenant}` drops the whole collection (+ Postgres cascade in prod).
- **Auditability** - Postgres audit log of ingest/access; OAuth 2.0 scopes on the MCP surface.

## Layout

```
app/retrieval_api.py   internal retrieval core (FastAPI) - the single source of truth
app/mcp_server.py      MCP server (Streamable HTTP + OAuth 2.0) - a parallel client
app/store.py           per-tenant vector store (Qdrant or in-memory fallback)
app/embedding.py       local embeddings (sentence-transformers or hashing fallback)
app/llm.py             local generation via Ollama/Qwen3 (extractive fallback)
tests/                 end-to-end tests (isolation, ranking, erasure)
docker-compose.yml     full stack: retrieval-api · mcp-server · qdrant · ollama · postgres
demo.py                seed + query walk-through
```

---
Reference implementation by Dr. Sandeep Grover. Illustrative demo - not the production repo.
