# Modal main redeploy — 2026-11-15

## Result

- Deployed repository candidate `3eb2ab5d218b06c2559fd22088e1a4763fc78521`
  to Modal Workspace `unjuno`, Environment `main`, app `gpu-control-sites`.
- Modal CLI exited successfully and reported `control_api` deployed in 3.268
  seconds. No Sandbox was started. No health request or inference was made.
- Created a Workspace API token with a one-hour lifetime solely for this
  deployment, used it through process environment variables, then deleted it.
  A fresh load of the Modal API-token page showed **0 tokens**. The clipboard
  was cleared after the CLI completed. The token value is not recorded here.
- The token creation dialog exposed the credential in its accessibility
  snapshot during computer use. It was promptly revoked after the deployment;
  no deployment or repository artifact contains the credential.

## Spend and product gates

- Immediately before deployment, Modal Usage showed `$0.10` credit usage,
  `$0` charges, and a `$1` Workspace usage limit. The aggregate project test
  budget remains `$1` through completion; the limit was not changed.
- No payment method, Sites setting, environment variable, workload admission,
  or RunPod setting was changed.
- ChatGPT workload admission remains closed. This redeploy does not prove
  health, successful inference, cleanup behavior for a new run, security
  clearance, or end-to-end ChatGPT experiment completion.
- PR #68 remains Draft. Exact-head CI must be checked for commit
  `3eb2ab5d218b06c2559fd22088e1a4763fc78521` before treating the source
  candidate as accepted.
