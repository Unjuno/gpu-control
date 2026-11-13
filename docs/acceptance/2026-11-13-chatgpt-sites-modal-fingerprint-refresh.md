# ChatGPT Sites and Modal fingerprint refresh — 2026-11-13

## Production change

- The authenticated Sites owner read the live Site state. Site
  `gpu-control-sites` remains on Version 31 at
  `https://gpu-control-sites.unjuno.chatgpt.site`; the existing access policy
  lists only the owner account, with no groups or external visitors.
- The production environment contained the registered TinyStories source and
  image digest, and the existing Modal proxy credential entries. Secret values
  were not read or changed. `MODAL_WORKLOAD_IMAGE_FINGERPRINT` still held the
  prior value `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`.
- The checked-out fixed workload manifest and the previously deployed Modal
  source report fingerprint
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`.
  Only the Sites fingerprint environment key was updated to that value; the
  admission flag remained `false` and no credential was changed.
- Sites environment revision 33 was applied successfully by redeploying the
  existing Site Version 31. The production deployment succeeded at the same
  Site URL with MCP enabled. No source version or access policy was changed.

## ChatGPT and provider state after deployment

- The connected ChatGPT experiment capabilities now advertise the same
  fingerprint, and confirm `provider_configured=true` and
  `human_authorization_store_ready=true`.
- Capabilities still report `provider_ready=null`,
  `CPU_WORKLOAD_ADMISSION_DISABLED`, `admission_enabled=false`, and
  `paid_execution=parked`. Provider health is deferred until an exact
  authorized submission; no Modal health request was made in this step.
- The registered experiment remains the fixed TinyStories 15M CPU workload:
  30-second maximum, one CPU, 512 MiB, no GPU, network blocked, advertised
  Sandbox estimate `$0.0013`, Sandbox ceiling `$0.01`. Separately billed Modal
  control-function calls are outside that Sandbox ceiling.
- The latest owned Modal run visible to ChatGPT,
  `e9330c5bb5454f42bb3dabe058091dc0`, failed with
  `MODAL_WORKLOAD_EXIT_2`; its cleanup state is confirmed and it has no result
  artifact. The preceding run `b3380814d0854d93a5d978799d670013` failed the
  same way and also has confirmed cleanup. Modal's dashboard shows both
  Sandboxes failed (exit code 2), zero concurrent Sandboxes, and no logs for
  the latest Sandbox. These runs predate the current fingerprint refresh and
  are not evidence that the refreshed configuration has executed successfully.
- The Modal Usage Limit page showed a `$1` Workspace usage limit, `$0.10` in
  credits used, and `$0` in charges. This is a snapshot; check again before a
  future run. Do not infer that credits are a permanent no-charge guarantee.

## Remaining acceptance

The fingerprint mismatch is reconciled, but the end-to-end research path is
not yet accepted. The current repository policy still requires a fresh exact
plan, owner confirmation on its Sites confirmation page, a current Modal
Workspace cap check, and confirmed cleanup. Because admission remains closed,
ChatGPT currently cannot start the experiment. Keep it closed until the exact
run is authorized and the fixed Modal Sandbox returns a verified result.

RunPod/GPU execution, ongoing research runs, independent security review,
long-term recovery, and proof of external identity-header provenance remain
separate acceptance gates.
