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
