# Public Site and ChatGPT read-only recheck — 2026-11-15 06:13 JST

## Site audience and ChatGPT tool reachability

- Read the existing Sites project `gpu-control-sites`: status `active`, Site
  Version 34, and access mode `public`. Its published URL is
  `https://gpu-control-sites.unjuno.chatgpt.site`. The current caller is the
  owner. The access record has one account-user allowlist entry and zero
  external visitors. No access setting was changed.
- Called the connected `GPU Control — ChatGPT実験管理` MCP tool
  `experiment_list` from this ChatGPT conversation. It returned `status=ok`
  with owner-scoped run history. This proves that this connected ChatGPT tool
  can reach the published Site and perform this read operation; it does not
  prove anonymous callers are denied at the platform boundary or that the
  injected identity cannot be spoofed.
- The five newest records labeled `execution_origin=modal_sandbox` are all
  `failed`. A read-only `experiment_result` call for the newest failed run
  returned `RESULT_NOT_READY` and the failed state. It is not a successful
  Modal inference and does not satisfy CPU execution acceptance.

## Boundaries and remaining acceptance

- Public Site reachability and an authenticated ChatGPT tool connection are
  compatible with owner-scoped execution. The Site URL alone is not proof of
  owner identity, write confirmation, or provider authorization.
- The currently connected `experiment_prepare` tool still directs the user to
  a Site confirmation link. The PR #68 ChatGPT-native exact-plan confirmation
  candidate is source-only and has not been published to the Site. No new
  plan, provider health call, Sandbox, D1/R2 mutation, or RunPod call was made.
- Cross-account denial, trusted provenance of the Sites-injected identity,
  hosted confirmation rendering, and the current Modal failure cause remain
  unverified. RunPod/GPU and paid training remain parked.

This is a read-only connectivity and owner-history check, not live execution
acceptance or a complete security clearance.

## Follow-up recheck — 2026-11-15

- From this ChatGPT conversation, `experiment_capabilities` returned `status=ok`:
  CPU admission is enabled, Modal is configured, and the registered workload is
  available. Its fixed limits are 1 physical CPU core, 512 MiB, and 30 seconds.
  The estimated Sandbox ceiling is `$0.01` (estimated `$0.0013`); Modal control
  function charges are separate. The provider readiness value is still null and
  its health check remains deferred until an authorized exact-plan submission.
  No health request, plan, or Sandbox was initiated.
- A fresh `experiment_list` showed the newest five Modal Sandbox runs failed.
  `experiment_result` for newest run `e9330c5bb5454f42bb3dabe058091dc0`
  returned `RESULT_NOT_READY`. Its failure cause was not exposed by that
  read-only result operation. Successful historical rows are labeled
  `retired_local_runner`, not Modal.
- The focused local Modal bootstrap/capture regression tests passed 10/10.
  This validates local code paths only, not the remote Modal image or inference.
- PR #68 remains Draft. Exact-head GitHub Actions for `2518bb78f01d0618ac29de5ed97677f753c23365`
  passed CI run 538 and Project bridge tests run 335. These checks do not deploy
  the ChatGPT-native confirmation candidate or establish live provider health.

The public Site and owner-connected ChatGPT read tools work without a separate
Site sign-in in this chat. The published confirmation flow still requires that
sign-in; the chat-native exact-plan approval remains undeployed. Public access
therefore does not yet make a new paid inference runnable from this conversation.
