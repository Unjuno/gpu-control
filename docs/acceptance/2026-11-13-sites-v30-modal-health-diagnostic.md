# Sites Version 30 — Modal health diagnostic — 2026-11-13

## Deployment evidence

- GitHub PR #68 candidate commit: `dbd4089bbe4e480dff283555638ce201cbd3c82e`.
  Its six required exact-head CI jobs passed. Local Site Worker tests passed
  **32/32**, Site build and artifact validation passed, and D1 migration replay
  passed.
- The Site source was opened from `6144d58acf6de609c8ac42d0b06542e29d89b1ab`,
  synchronized to the candidate, tested and packaged from the dedicated Site
  checkout. Site source commit: `b97c5ceaad1d509c262d66a07015f74bb4e17546`.
- Saved as Site Version 30 with archive content hash
  `sha256:2e2fd6c3c1a06ffda77397e39b4032e022cf8d839f61ba77350317d2b1eed1e8`;
  the production deployment succeeded at
  <https://gpu-control-sites.unjuno.chatgpt.site> with MCP enabled and
  environment revision 32.
- Live D1 overview lists `modal_health_check_limits`. Live environment still
  has `CPU_WORKLOAD_ADMISSION_ENABLED=false`, previous registered image digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`,
  and previous fingerprint
  `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`.
  No environment variables or secrets were changed.

## What this verifies and what remains

Version 30 includes owner-allowlisted `experiment_provider_health`, which
performs a bearer-authenticated Modal health GET, compares the returned
registered workload identity, and never creates a Sandbox. A global D1-backed
60-second cooldown limits health calls, and the tool schema discloses separate
Modal control-function billing.

The current ChatGPT GPU Control connector in the deployment session still
exposes the previous tool schema. Therefore the new operation has not been
invoked through ChatGPT, authenticated Modal health remains unverified, and no
health request or Sandbox was started. The source-level mock tests do not prove
the production Modal token works. Keep admission disabled until the connected
ChatGPT tool list refreshes, the one bounded health diagnostic reports matching
identity, and image digest/fingerprint reconciliation is complete.
