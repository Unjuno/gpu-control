# Modal capture hardening — 2026-11-14

## Finding and fix

An independent read-only review found that `modal/app.py::_capture` assumed the
final JSON line from Sandbox stdout was an object. Valid JSON values such as
`[]`, `null`, or a string raised on `.get()` before `sandbox.terminate()`, so an
unexpected output format could leave cleanup unattempted and the run without a
cleanup receipt.

The candidate now accepts only a complete JSON object. Polling and output-stream
errors are converted to a bounded `CAPTURE_FAILED` result, and execution
continues to Sandbox termination. Provider exception text is not returned.
Regression tests exercise non-object JSON and a stream that fails after
yielding partial output; both end in a failed run with confirmed termination.

## Verification

- `uv run --locked pytest tests/test_modal_capture.py tests/test_modal_bootstrap.py`:
  10 passed, 5 subtests passed.
- `uv run --locked pytest`: 588 passed, 1 skipped, 5 subtests passed.
- `npm test --prefix sites/gpu-control-sites`: 42 passed.
- `git diff --check` and Python compilation passed.
- All six GitHub checks passed for head
  `bc1035df4a72d12b8347f549bf30b970ebdf48d6`.

## Runtime status

This code has not yet been redeployed to Modal. The live Sites remains at
Version 33, environment revision 36, with CPU admission disabled. No provider
health call or Sandbox was started to validate this patch. The previous five
Modal attempts failed with `MODAL_WORKLOAD_EXIT_2`; the latest recorded cleanup
was confirmed and produced no artifact. Their failure cause is not established.

The aggregate test budget remains `$1`; Modal Usage currently shows `$0.10` in
credits, `$0` in charges, and a `$1` Workspace usage limit. The per-Sandbox
`$0.01` ceiling does not include separate Modal control-function charges.

## Related independent review notes

- The Sites auth and D1 ownership paths inspected had no confirmed actionable
  flaw. A denial test from another authenticated account and authoritative
  identity-header provenance remain open.
- No additional RunPod adapter flaw was confirmed in the inspected REST client,
  authorization, reconciliation, and cleanup code. RunPod is not wired to the
  live Site and remains parked.
- CI workflow review found no actionable issue in the inspected workflows.
  The CPU reference container's floating Python base tag remains a
  reproducibility limitation before any GPU promotion.
- The repository-wide security review is still partial at 45 of 335 files and
  has no final report; these focused reviews do not constitute security
  clearance.

## Stale Modal run-slot recovery — follow-up

An independent D1/R2 recovery audit found that a persistently missing Modal
Sandbox left a run in `running` forever. The unique active-run index then
blocked every subsequent submission. A transient 404 must still preserve the
reservation because the original submit may have succeeded with a lost reply.

The Worker now keeps the reservation until the recorded lease has expired plus
a 300-second recovery grace. Only a subsequent authenticated Modal not-found
response can conditionally move that same still-running, cleanup-pending lease
to `failed`, set `cleanup_state=confirmed`, and record a bounded evidence
receipt. The update is fenced by run owner, observed lease expiry, active state,
and pending cleanup; a transient not-found before the horizon leaves the slot
occupied. This grace exceeds Modal's documented 150-second Web Function HTTP
request window and the workload's 30-second maximum Sandbox lifetime. See
[Modal Web Function request timeouts](https://modal.com/docs/guide/webhook-timeouts)
and [Sandbox lifetime](https://modal.com/docs/guide/sandboxes).

Regression coverage proves a 404 before the horizon retains the slot and a 404
at the horizon releases it with failure and cleanup evidence. The prior lost
submit test still proves that a transient 404 followed by finding the original
Sandbox does not create a duplicate. Sites Worker tests pass 43/43; the Site
build and artifact validation pass.

The fix is not deployed. Sites Version 33 remains live with CPU admission
disabled; no Modal call or Sandbox was made for this change. This controlled
recovery only runs when the authenticated owner requests status, so it does
not create background provider traffic or unobserved control-function cost.
