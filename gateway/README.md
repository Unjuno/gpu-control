# Legacy Python Gateway

This package is retained for local integration, recovery, and security evidence. It is **not** the ChatGPT-facing production endpoint. Do not deploy it to Vercel or connect it to Neon.

The active ChatGPT service is the private Sites app: a Cloudflare Worker with D1 for plans, idempotency, run state, leases, and Runner heartbeats, R2 for result artifacts, and the macOS Runner for registered local CPU experiments.

The old Vercel entrypoint, comment-trigger Gateway route, Docker API image, and deployment instructions are preserved under [`docs/archive/legacy-vercel-gateway/`](../docs/archive/legacy-vercel-gateway/). PostgreSQL code, recovery tests, and Linux deployment templates belong to that legacy Python service; none is a dependency of the Sites runtime, and the current path does not require a Neon account.

Keep provider GPU execution parked. Porting a useful legacy control into the Sites Worker requires a separate design and security review before activation.
