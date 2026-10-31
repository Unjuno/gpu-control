# MCP Python SDK interoperability smoke

Status: **PASS for local Streamable HTTP protocol interoperability only; real ChatGPT acceptance NOT RUN**.

## Evidence

- Gateway candidate base: `316c1bdd633b2bcc8251544e0b8738af76eb244f` plus the uncommitted protocol change recorded in this candidate.
- Client: official `mcp` Python SDK `2.3.0`, with `httpx2` Streamable HTTP transport.
- Server: local Uvicorn process bound to `127.0.0.1`; request crossed the real HTTP transport and MCP negotiation path.
- Negotiated protocol: `2026-07-28`.
- `tools/list`: returned all 8 canonical `experiment_*` tools.
- `experiment_capabilities`: SDK call completed with `is_error=false`.
- Authentication: a short-lived local fixture JWT and test signing key were used. This does not exercise browser OAuth, ChatGPT OAuth, refresh, or revocation.
- Guardrail: only the read-only capabilities tool was called; no experiment was prepared or submitted, and no provider was contacted.
- Commands:
  - `PYTHONPATH=gateway gateway/.venv/bin/python /tmp/gpu-control-mcp-sdk-smoke.py`
  - `gateway/.venv/bin/python -m pytest gateway/tests/test_http_auth.py -q`
- Outcome: SDK smoke passed after adding modern cache hints. The HTTP authentication/protocol regression suite passed.

## Finding and correction

The first SDK attempt negotiated `2026-07-28` but rejected `tools/list` because the response omitted required `cacheScope` and `ttlMs`. The current protocol response already included `resultType`. Modern `server/discover` and `tools/list` now return `cacheScope: "private"` and `ttlMs: 0`: the list varies with the caller's scopes, and a zero TTL avoids reuse after authorization changes.

The initial failure was reproduced before the correction; the passing smoke and regression suite were run after it. These results establish compatibility with this official SDK version and the covered read-only path. They do not establish compatibility with ChatGPT's production OAuth client or user interface.

## Still required for P1 acceptance

Real ChatGPT account/workspace authorization, OAuth authorization and refresh/reconnect, deployed HTTPS endpoint, durable database and independent worker, registered CPU prepare/submit/result/artifact flow, cancellation/recovery, cross-conversation retrieval, and independent release review remain open in `docs/CHATGPT_ACCEPTANCE.md`.
