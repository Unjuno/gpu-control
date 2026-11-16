# Gateway directory

The supported ChatGPT experiment-control path is the private Sites MCP Worker
with D1. It is implemented in [`../sites/gpu-control-sites`](../sites/gpu-control-sites)
and its current status and acceptance gates are in
[`../docs/decisions/2026-11-11-sites-d1-architecture-pivot.md`](../docs/decisions/2026-11-11-sites-d1-architecture-pivot.md).

The FastAPI/PostgreSQL implementation in this directory is retained only as a
legacy behavior and test reference. Do not deploy it or provision new Vercel,
Neon, or PostgreSQL resources for the product. Historical implementation and
acceptance evidence remains in Git history and dated records under `../docs/`;
there is no active Vercel or Neon setup guide in this repository.

Current hosted acceptance is a bounded, free CPU smoke through ChatGPT and
Sites. Recovery, artifact storage, cross-owner isolation, real model inference,
and GPU execution remain separate open gates. Paid execution remains parked.
