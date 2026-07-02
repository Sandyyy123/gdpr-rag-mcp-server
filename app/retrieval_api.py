"""
Internal retrieval API - the central core.

This is the single source of truth for retrieval and answering. It owns query
embedding, per-tenant vector search, prompt assembly, and the local LLM call.
The MCP server and the (later) custom UI both attach to THIS contract as parallel
clients - they contain no retrieval logic of their own.

Contract (stable, versioned):
    POST /v1/ingest    {tenant, doc_id, text, meta}   -> index a document chunk
    POST /v1/retrieve  {tenant, query, top_k}         -> ranked source chunks
    POST /v1/answer    {tenant, query, top_k}         -> grounded LLM answer + sources
    DELETE /v1/tenant/{tenant}                        -> GDPR erasure (drop collection)
    GET  /v1/tenants                                  -> list tenants
    GET  /healthz
"""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .embedding import embed
from .llm import generate_answer
from .store import get_store

app = FastAPI(title="GDPR RAG Retrieval Core", version="1.0.0")
store = get_store()


class IngestReq(BaseModel):
    tenant: str
    doc_id: str
    text: str
    meta: dict = {}


class RetrieveReq(BaseModel):
    tenant: str
    query: str
    top_k: int = 4


class AnswerReq(BaseModel):
    tenant: str
    query: str
    top_k: int = 4


@app.get("/healthz")
def healthz():
    return {"status": "ok", "store": type(store).__name__}


@app.post("/v1/ingest")
def ingest(req: IngestReq):
    store.upsert(req.tenant, req.doc_id, embed(req.text),
                 {"text": req.text, **req.meta})
    return {"ingested": req.doc_id, "tenant": req.tenant}


@app.post("/v1/retrieve")
def retrieve(req: RetrieveReq):
    hits = store.search(req.tenant, embed(req.query), req.top_k)
    return {"tenant": req.tenant, "query": req.query, "results": hits}


@app.post("/v1/answer")
def answer(req: AnswerReq):
    hits = store.search(req.tenant, embed(req.query), req.top_k)
    contexts = [h["payload"].get("text", "") for h in hits]
    text = generate_answer(req.query, contexts)
    return {
        "tenant": req.tenant,
        "query": req.query,
        "answer": text,
        "sources": [{"id": h["id"], "score": round(h["score"], 4)} for h in hits],
    }


@app.delete("/v1/tenant/{tenant}")
def erase(tenant: str):
    dropped = store.drop_tenant(tenant)
    return {"tenant": tenant, "erased": dropped}


@app.get("/v1/tenants")
def tenants():
    return {"tenants": store.tenants()}
