"""
MCP server - a PARALLEL CLIENT of the retrieval core, not a link in a chain.

It holds zero retrieval logic. Every tool call is forwarded over HTTP to the
internal retrieval API (the same contract the future custom UI will call). This
is the whole point of the architecture: swap or add a client without touching
retrieval; improve retrieval once and every client benefits.

Transport: Streamable HTTP (no SSE). OAuth 2.0 bearer tokens are validated per
call and carry the tenant scope, so a client can only reach its own tenant.

Run:  uvicorn app.mcp_server:app --port 8080
"""
from __future__ import annotations

import os

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

RETRIEVAL_API = os.getenv("RETRIEVAL_API_URL", "http://localhost:8000")

app = FastAPI(title="GDPR RAG MCP Server", version="1.0.0")


# --- OAuth 2.0 (bearer) -> tenant scope -------------------------------------
def resolve_tenant(authorization: str = Header(default="")) -> str:
    """Validate the OAuth 2.0 bearer token and return the tenant it is scoped to.

    Demo: a token maps to a tenant via OAUTH_TOKENS ("token:tenant,token:tenant").
    Production: introspect against the OAuth server / Postgres client table.
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    mapping = dict(
        pair.split(":", 1)
        for pair in os.getenv("OAUTH_TOKENS", "demo-token:acme").split(",")
        if ":" in pair
    )
    tenant = mapping.get(token)
    if not tenant:
        raise HTTPException(403, "invalid or unscoped token")
    return tenant


class ToolCall(BaseModel):
    name: str
    arguments: dict = {}


# --- MCP tool discovery (Streamable HTTP) -----------------------------------
TOOLS = [
    {
        "name": "search_knowledge",
        "description": "Retrieve the most relevant source chunks for a query from the caller's tenant.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 4}},
            "required": ["query"],
        },
    },
    {
        "name": "answer_question",
        "description": "Get a grounded, German-language answer with sources for a query.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 4}},
            "required": ["query"],
        },
    },
]


@app.get("/mcp/tools")
def list_tools(tenant: str = Depends(resolve_tenant)):
    return {"tools": TOOLS}


@app.post("/mcp/call")
def call_tool(call: ToolCall, tenant: str = Depends(resolve_tenant)):
    """Forward the tool call to the retrieval core, scoped to the token's tenant."""
    args = call.arguments
    if call.name == "search_knowledge":
        resp = requests.post(
            f"{RETRIEVAL_API}/v1/retrieve",
            json={"tenant": tenant, "query": args["query"], "top_k": args.get("top_k", 4)},
            timeout=120,
        )
    elif call.name == "answer_question":
        resp = requests.post(
            f"{RETRIEVAL_API}/v1/answer",
            json={"tenant": tenant, "query": args["query"], "top_k": args.get("top_k", 4)},
            timeout=180,
        )
    else:
        raise HTTPException(404, f"unknown tool: {call.name}")
    resp.raise_for_status()
    return {"tool": call.name, "tenant": tenant, "result": resp.json()}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "retrieval_api": RETRIEVAL_API}
