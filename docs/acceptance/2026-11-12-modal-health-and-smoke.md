# Modal health and bounded CPU smoke — 2026-11-12

## Result

The fixed Modal API was deployed from commit `d09fab0` after correcting the
remote source-root resolution. The authenticated health endpoint returned
HTTP 200, and ChatGPT `experiment_capabilities` reported
`provider_ready=true` with the registered image fingerprint. The focused
security diff review of `sites/gpu-control-sites/modal/app.py` completed with
zero reportable findings; it covered that file only.

## Bounded ChatGPT attempt

For one smoke attempt, production `CPU_WORKLOAD_ADMISSION_ENABLED` was changed
from `false` to `true`, and saved Site Version 23 was redeployed. ChatGPT
prepared run `96d7efef9542463d9fc51f47ffbfd5d7` for the registered
`tiny-stories-inference-v1` workload with a 30-second runtime limit, 8-token
limit, and `$0.00` requested maximum cost. No GPU was requested.

The Modal Sandbox was created and started, then exited after 419 ms with code
2. The Modal UI showed no stdout/stderr for the Sandbox. ChatGPT status recorded
`state=failed`, `failure_code=MODAL_WORKLOAD_FAILED`, and
`cleanup_state=confirmed`; the result artifact was not produced. Modal showed
zero live Sandboxes afterward. The Modal app usage panel displayed `$0.00` for
this cycle at the time of inspection.

The Modal deploy API token was deleted from the workspace after deployment.
Production admission was restored to `false`, and Version 23 was redeployed
with environment revision 20. A final capabilities call confirmed
`provider_ready=true`, `admission_enabled=false`, and
`blocking_reason=CPU_WORKLOAD_ADMISSION_DISABLED`.

## Remaining work

The Sandbox exit code 2 corresponds to a preflight rejection in
`workloads/tiny_stories_inference/inference.py`; the current implementation
returns that code without a diagnostic label. The exact failed preflight check
is therefore unknown. Add a bounded, non-sensitive diagnostic code, validate
it against the Modal Sandbox environment, then repeat the one-run CPU
acceptance. Keep admission disabled until that focused fix is ready. GPU and
RunPod execution remain parked and unverified.

This record establishes authenticated Modal health and one failed bounded
Sandbox attempt. It does not establish successful Modal inference, GPU use,
RunPod integration, a billing guarantee, cross-account authorization, or
long-duration reliability.
