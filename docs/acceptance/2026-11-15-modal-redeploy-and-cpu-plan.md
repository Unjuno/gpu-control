# Modal redeploy and CPU plan checkpoint — 2026-11-15

## Modal deployment

- Re-deployed candidate commit `66010298af1cad4c40a45c0463f7e31e56db5da4`
  to Modal Workspace `unjuno`, Environment `main`, App `gpu-control-sites`.
  The Modal CLI reported a successful deploy in 3.328 seconds and returned the
  existing `control_api` endpoint.
- No Sandbox was created and no post-deploy health or inference request was
  made. The existing `/v1/health` route and workload readiness therefore remain
  unverified after this deployment.
- The candidate contains no Modal runtime-code delta relative to
  `6a024f5b584e85efa93cf6df3cd0fa827f833bc2`; the redeploy does not establish
  that the observed workload exit code 2 has been fixed.
- The logged-in Modal UI showed 0 live containers and 0 running calls after the
  deployment.

## Credential handling

- The first one-hour token creation view included its credential in the
  computer-use accessibility output. That token was not used and was deleted.
- A second one-hour Workspace token was used only through process environment
  variables for the `main` deployment. It was deleted immediately after the
  successful deploy. The refreshed API-token page showed 0 tokens.
- The copied credential command was cleared from the clipboard. The temporary
  CLI virtual environment and deploy helper were removed. No token value is
  included in this record or repository.

## Spend and admission

- After deployment, Modal Usage showed `$0.10` of credits used, `$0` in charges,
  and the Workspace usage limit at `$1`. No payment method or budget setting was
  changed.
- ChatGPT `experiment_capabilities` still reports
  `CPU_WORKLOAD_ADMISSION_DISABLED`, `available=false`, and defers provider
  health checks until an authorized exact-plan submission. Admission remains
  closed.
- The latest Modal-origin run remains failed with `MODAL_WORKLOAD_EXIT_2`,
  confirmed cleanup, and no result artifact. The Modal log page queried for
  that Sandbox showed no logs.

## Next exact-plan gate

- Prepared run `16fc88de7ef44e88957f58ffd8e88035` for the registered
  TinyStories 15M workload against source `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`:
  prompt `Once`, one generated token, seed `61112`, 30 seconds, CPU only, no
  network, 1 physical core, and 512 MiB.
- Plan fingerprint:
  `c8876c8305b2d31975e9a3ceb425bdfd840367385a0120290a36404264337d0d`.
  Sandbox estimate is `$0.0013`, with a `$0.01` Sandbox-only ceiling. Modal
  control-function charges are excluded. This does not mean `$1` per run; the
  authorized project budget remains `$1` aggregate through completion.
- The plan requires explicit confirmation by the authenticated owner on its
  Sites authorization page and expires after 10 minutes. It has not been
  submitted; no new Sandbox or health call has started.

## Remaining release gates

- The repository-wide P0 security scan remains incomplete because the managed
  read-only worker could not start under the current filesystem profile.
- RunPod remains disabled: the provider lacks a trusted completion-signing
  protocol that keeps signing material outside the Pod while binding exact
  results and provider-observed lifecycle facts.
- Do not mark ChatGPT experiment completion until the owner-confirmed CPU run
  yields a result, cleanup and budget are checked, cross-account access is
  verified, and required security review is complete.
