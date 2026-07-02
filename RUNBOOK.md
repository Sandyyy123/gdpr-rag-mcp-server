# Runbook - GDPR RAG/MCP Knowledge Server

Operational guide for the German host (Hetzner GEX44).

## Deploy

```bash
git clone <your-repo> && cd gdpr-rag-mcp-server
docker compose up -d
docker compose exec ollama ollama pull qwen3:14b      # one-time model pull
curl localhost:8000/healthz                            # core up
curl -H "Authorization: Bearer demo-token" localhost:8080/mcp/tools   # MCP up
```

## Operate

- **Ingest a document chunk**
  ```bash
  curl -X POST localhost:8000/v1/ingest \
    -H 'content-type: application/json' \
    -d '{"tenant":"acme","doc_id":"doc-1","text":"...","meta":{"source":"handbuch.pdf"}}'
  ```
- **Ask via MCP (tenant comes from the OAuth token, not the request body)**
  ```bash
  curl -X POST localhost:8080/mcp/call \
    -H 'Authorization: Bearer demo-token' -H 'content-type: application/json' \
    -d '{"name":"answer_question","arguments":{"query":"Was ist der GEX44?"}}'
  ```

## GDPR - erase one tenant (right to erasure)

```bash
curl -X DELETE localhost:8000/v1/tenant/acme     # drops the Qdrant collection
# then cascade-delete the tenant's rows in Postgres (documents, audit) in prod
```

## Backup

- **Qdrant**: snapshot the `qdrant_data` volume (or Qdrant snapshot API).
- **Postgres**: `docker compose exec postgres pg_dump -U rag rag > backup.sql`.

## German answer-quality regression

Point the eval client at `/v1/answer` with your provided test-question set; compare answers
against expected, record pass rate per release. Run it in CI on every change.

## Health / troubleshooting

| Symptom | Check |
|---------|-------|
| Answers slow | `docker compose logs ollama`; confirm GPU passthrough is enabled |
| Empty results | Was the tenant ingested? `GET /v1/tenants` |
| 401/403 on MCP | Bearer token missing or not scoped to a tenant (`OAUTH_TOKENS`) |
| Core down | `docker compose logs retrieval-api`; `GET /healthz` |

## Security notes

- No external LLM/embedding calls - all inference is local.
- Replace the demo `OAUTH_TOKENS` map with real OAuth 2.0 token introspection before production.
- Keep the host firewalled; expose only the MCP/UI ports you need.
