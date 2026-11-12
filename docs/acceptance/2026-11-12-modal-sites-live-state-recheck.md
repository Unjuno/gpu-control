# Modal and ChatGPT Sites live state recheck

Checked: 2026-11-12 09:28 UTC

## ChatGPT tool path

Read-only calls to the installed `GPU Control — ChatGPT実験管理` MCP returned:

- `experiment_capabilities`: `provider_ready=true`,
  `admission_enabled=false`, `available=false`, blocker
  `CPU_WORKLOAD_ADMISSION_DISABLED`; provider `modal_cpu`; workload
  `tiny-stories-inference-v1`; max runtime 30 seconds; max inflight 1; paid
  execution parked.
- `experiment_list`: latest failed runs were `96d7efef9542463d9fc51f47ffbfd5d7`
  (created 2026-11-12 08:21 UTC) and
  `599473dcc1ed4034a42d849bcb42e261` (created 2026-11-12 08:52 UTC). Both
  report `MODAL_WORKLOAD_FAILED`, `cleanup_state=confirmed`, and no result.
- The latest listed success, `eacc26ff2ad54cf69a1ee7665325b197` (created
  2026-11-12 05:02 UTC), has a validated TinyStories CPU result and confirmed
  cleanup. It predates the current Modal deploy and does not verify the
  launcher fix.

## Modal dashboard

- Workspace banner: `$0.98` credits; adding a payment method is
  needed to unlock the remainder. This is a credit balance notice, not a hard
  spend-stop guarantee.
- App overview at the time of inspection: deployment shown as 22 minutes old,
  `$0.02` usage this cycle, 0 live containers, 0 live Sandboxes. The function
  deployment timeline identifies the current deployment as v4 at
  2026-11-12 18:06:03 JST. The history row leaves its commit field blank; v3
  shows `740fa98`, so the dashboard alone does not bind v4 to a source commit.
- The `control_api` function showed recent `/v1/health` calls returning HTTP
  200. The app overview does not expose a source commit in the inspected view,
  so the live deployment cannot be tied to the latest Git commit from this
  evidence alone. Both failed runs above (17:21 and 17:52 JST) predate v4; the
  listed successful run at 14:02 JST also predates v4. None accepts current v4.

## Gate disposition

No CPU run was submitted because admission is currently false and the exact
post-fix retry remains separately authorized. The objective remains open:
verify which source is deployed, then run the bounded ChatGPT CPU lifecycle,
retrieve its artifact, validate its provenance, and confirm cleanup. Recovery,
cross-account isolation, Runpod GPU, and paid execution remain separate gates.
