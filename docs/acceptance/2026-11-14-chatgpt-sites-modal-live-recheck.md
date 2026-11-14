# ChatGPT Sites and Modal live recheck — 2026-11-14

## Persistent ChatGPT connection

- The existing Site is `gpu-control-sites` at
  `https://gpu-control-sites.unjuno.chatgpt.site`, Site Version 33. Its platform
  access mode is public, with the authenticated owner account ID as the only
  allowlisted account and no groups or external visitors.
- ChatGPT's registered experiment capability and owner-scoped run-list tools
  responded successfully. The Site reports its Modal provider as configured;
  secret values were masked and not read.
- The Site is therefore persistently connected to the provider control plane;
  reconnecting the ChatGPT app or re-entering a provider credential for each
  chat is not required. Exact-plan owner confirmation remains a separate,
  per-experiment safety gate.

## Admission and provider evidence

- The current Sites environment originally reported
  `CPU_WORKLOAD_ADMISSION_ENABLED=true`, while the deployed Modal API/Sandbox
  did not yet have verified hard CPU and memory limits matching the advertised
  Sandbox cost ceiling. Admission was changed to `false` at environment
  revision 35 and Site Version 33 was redeployed successfully as deployment
  `appgdep_6af73b97f0548191a7f9324e93dc1e6d`.
- A post-deployment ChatGPT capability call returned
  `CPU_WORKLOAD_ADMISSION_DISABLED`, `admission_enabled=false`, and
  `available=false`, confirming that new runs are stopped while the saved
  ChatGPT connection and owner authentication continue to work.
- The Site still advertises Modal API fingerprint
  `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec` and
  workload digest
  `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  The current repository candidate includes explicit Sandbox resource bounds
  (`cpu=(1.0, 1.0)`, `memory=(512, 512)`) and its documented fingerprint is
  `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`. These
  candidate values are not yet live or health-verified.
- The latest recorded Modal-origin run,
  `e9330c5bb5454f42bb3dabe058091dc0`, failed with
  `MODAL_WORKLOAD_EXIT_2`, has confirmed cleanup, and has no result artifact.
  The Modal dashboard had no logs for that Sandbox. No Sandbox was started in
  this recheck.

## Billing and credentials

- Modal's Usage Limit page showed `$0.10` in credits, `$0` in charges, and a
  `$1` Workspace usage limit set by Modal. The page offered adding a payment
  method to raise that limit; no separate net-spend limit was shown.
- Modal's general Starter pricing advertises `$30` monthly compute. The
  account-specific dashboard currently says `$1` of `$30/mo` is available, while
  its Credits tab says `$1` monthly. Treat the account UI as authoritative for
  the unlocked amount; do not assume the full public `$30` allotment is usable.
  The user authorized up to `$1` total project testing usage. Preserve the
  existing `$1` Workspace cap and do not add a payment method. The `$0.10`
  already used this period leaves at most `$0.90` under that cap for subsequent
  usage, including separately billed control-function calls.
- Modal's member API token page showed zero active member API tokens. The
  long-lived provider credential used by the Site is a separate, masked Proxy
  Token configuration. No unbounded Workspace API token was created.
- The advertised `$0.01` ceiling covers Sandbox CPU/memory only; Modal control
  function calls are separately billed and remain outside that ceiling.

## Repository and release state

- PR #68 remains Draft at head
  `0e719ebf27adebaf319bb7d684d08889debf045f`. Exact-head GitHub Actions runs
  for `CI` and `Project bridge tests` completed successfully. The exact
  two-file image-fingerprint acceptance diff completed a Codex Security diff
  review with zero findings.
- The repository-wide P0 audit remains partial, PR #68 has no submitted GitHub
  review, and the current candidate has not been deployed to Modal. No claim of
  full security clearance or successful live inference is made.

## Next acceptance steps

1. Finish review of the complete candidate and repository-wide P0 scope.
2. Deploy the reviewed Modal source to `unjuno/main` with a short-lived
   Workspace token, then revoke the token immediately.
3. Verify authenticated health reports the exact candidate fingerprint and
   inspect a real Sandbox to confirm CPU 1, memory 512 MiB, network isolation,
   and cleanup.
4. Reconcile the Sites fingerprint/digest and confirm a fresh exact plan before
   reopening admission or submitting a bounded CPU inference from ChatGPT.
5. Keep RunPod, GPU, and broader paid execution parked until their independent
   authorization, billing, resource, and cleanup gates are met.

## Follow-up — current ChatGPT and billing check

- A fresh ChatGPT capability call still reports `provider_configured=true`,
  while `admission_enabled=false` and `available=false`. This confirms the
  persistent Site/provider connection remains present while new executions are
  blocked pending the reviewed image/API reconciliation.
- The Modal Usage Limit page again showed `$0.10` in credits, `$0` in charges,
  and the `$1` Workspace usage limit set by Modal. It offered “Add a payment
  method” to raise the limit. No separate net-spend setting was visible, and
  no billing setting was changed.
- The exact-head CI workflows above passed; PR #68 has no submitted GitHub
  review. A full PR security review and the repository-wide P0 audit are still
  incomplete. No inference or Sandbox was started during this check.
