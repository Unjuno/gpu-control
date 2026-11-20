# P0 repository scan and Sites Version 35 publication — 2026-11-15

## Repository security audit

- Codex Security Standard scan `622fe374-d961-4ee7-8ced-15281ac89ebe`
  completed against immutable Git revision
  `26c1deff1f73924a3cf88592bdcc8bedf0970285`.
- The audit covered the 348-file repository inventory with three independent
  source-review packets and Semgrep `p/security-audit` plus `p/secrets` over
  295 tracked parsable targets. It reported **zero source-backed findings**.
- Semgrep's one alert was the documented SHA-1 reproduction of a Git blob
  object ID in `project_control/runner.py`; it is not used for a signature,
  credential, authorization decision, or security token and is explicitly
  called with `usedforsecurity=False`.
- The sealed report is stored outside the repository in the Codex Security
  workbench. Live Sites identity-header provenance, deployed environment
  values, Modal/RunPod account behavior, and provider cleanup remain runtime
  acceptance gates and were not claimed by this offline audit.
- Reported token measurement was partial because some rollout accounting was
  unavailable: 7,004,586 input tokens, 6,687,872 cached input tokens, and
  7,028,422 total tokens across the measured threads.

## Sites source and publication

- Opened the Site-owned source repository and compared live Version 34 source
  commit `18339d5106ff148d0ec4b3acf8da64791b69d54f` with the reviewed GitHub
  candidate. The intended delta was migration `0011`, the exact-plan
  ChatGPT-native write-confirmation contract, its tests, artifact validation,
  and documentation.
- Before publication, the Sites checkout passed `git diff --check`, all
  **44/44** Worker tests, the Worker build, and artifact validation.
- Pushed Site source commit `0eb4fe4ba7dcdc6035af4bdc89f8751b40716538`,
  saved Version 35, and deployed it successfully as production deployment
  `appgdep_6af8e7ce2cec81919ad697365bed2d7b`.
- Production remains public at
  <https://gpu-control-sites.unjuno.chatgpt.site>. The audience, owner
  allowlist, secrets, and environment values were not changed. MCP publication
  is ready and environment revision 39 was retained.
- A read-only D1 schema check showed `authorization_source` on
  `human_authorizations`, proving migration `0011_chatgpt_tool_authorization.sql`
  was applied. The owner-connected ChatGPT capability call succeeded and still
  reports Modal configured, the authorization store ready, admission enabled,
  one CPU core, 512 MiB, and the `$0.01` Sandbox-only ceiling.

## Remaining CPU acceptance

The current conversation loaded the plugin's pre-publication submit schema, so
it cannot yet send Version 35's required `approved_plan` argument. A fresh
ChatGPT conversation must load the refreshed plugin tool list, prepare one new
exact plan, show the destructive write confirmation, and run the bounded CPU
inference. Completion still requires a verified result, R2 artifact digest,
confirmed cleanup, and a post-run budget check. No provider health request,
Sandbox, RunPod call, GPU allocation, or new spend occurred in this checkpoint.
