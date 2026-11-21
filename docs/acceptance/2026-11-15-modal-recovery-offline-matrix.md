# Modal recovery offline matrix — 2026-11-15

## Scope

This record covers deterministic source-level recovery behavior for the fixed
Sites to Modal CPU route after the first accepted live CPU run. It does not
claim that the unpublished asynchronous candidate has passed a second live
run, forced provider restart, or live cancellation drill.

## Injected failure matrix

| Failure or race | Deterministic evidence | Expected safe state |
| --- | --- | --- |
| Parallel or duplicate authorization/submit attempt | Worker reserves one plan health call and one durable run; deterministic Modal Sandbox naming prevents replacement compute | At most one provider submission and one occupied slot |
| Lost submit response after provider acceptance | Worker leaves the durable run running, never blindly resubmits, and later status attaches the original Sandbox ID | Recoverable `running`, cleanup `pending` until provider observation |
| Normal asynchronous provider acceptance | Modal `/submit` returns `running`, Sandbox ID, image identity, and `cleanup_state=pending` without reading output or terminating; `/status` owns capture and cleanup | Short submit response followed by status-driven terminalization |
| Status observation timeout | Public response is generic; the durable run remains `running`, failure unset, and cleanup `pending` | Retryable observation with no invented terminal state |
| Repeated provider `not_found` | Run remains occupied through its bounded lease and recovery grace; only a fenced post-horizon observation records failure and an absence receipt | No early slot reuse; deterministic failed terminal state after horizon |
| Provider workload failure | Only allowlisted exit/diagnostic codes are stored; provider stderr is not exposed | Failed with confirmed cleanup; never promoted to a result |
| Wrong image fingerprint | Worker rejects the provider result before artifact persistence | Failed with confirmed cleanup and no R2 artifact |
| R2 write failure | First status call remains visibly failed/retryable; a later status call re-reads the same deterministic Sandbox result | No successful D1 row without its artifact |
| D1 finalization failure | R2 write may repeat, but later status reconciles the same result and commits success once | No false success before durable finalization |
| Cancellation/result race | Success uses a conditional D1 update; when cancellation wins, the uncommitted R2 object is removed | Cancellation cannot coexist with a published success artifact |
| Queued or running cancellation | Queued work terminates locally without provider cleanup; running work records a cooperative cancel request and provider cleanup remains status-driven | Owner-scoped, idempotent cancellation |

## Reproducible checks

From the repository root:

```sh
npm --prefix sites/gpu-control-sites test
npm --prefix sites/gpu-control-sites run build
npm --prefix sites/gpu-control-sites run validate
uv run pytest -q tests/test_modal_capture.py tests/test_modal_bootstrap.py
```

At source head `1ed33f6`, the pre-record checks passed with 45 Sites tests and
11 focused Python tests. The asynchronous Modal source candidate is committed
in the Site-owned history, but publication and a repeat live run remain open.

## Remaining live acceptance

Before calling recovery and operations accepted:

1. publish the asynchronous Site/Modal candidate without changing the owner
   allowlist or Workspace `$1` cap;
2. run one newly confirmed fixed CPU plan and observe a non-ambiguous submit
   response, terminal result, digest-verified artifact, and confirmed cleanup;
3. perform a bounded cancellation or forced-observation-loss drill and prove
   no live Sandbox or orphaned D1/R2 state remains;
4. re-read Modal active Sandboxes and billing after each provider operation;
5. retain admission and exact one-use plan confirmation instead of exposing
   anonymous public compute.

## Read-only live refresh

After recording the matrix, the authenticated ChatGPT tools were queried
without preparing a plan, checking provider health, or starting compute.
Capabilities still reported the fixed Modal CPU route available with admission
enabled, explicit one-use plan confirmation, one physical CPU core, 512 MiB,
30 seconds maximum runtime, estimated maximum Sandbox cost `$0.0013`, and the
`$0.01` Sandbox ceiling. The latest 50 owner-visible D1 records contained no
`queued` or `running` run; the newest record was the accepted Modal success
`245d034977e5471aa7ec6d1f80f6232f`.

This proves only the owner-visible Site/D1 state at the observation time. It
does not replace a provider-side Modal active-Sandbox inventory or billing
refresh, and no provider health call or spend was triggered by this read.
