# Modal `main` API deployment — 2026-11-13

## Outcome

PR #68 head `496e28cdb1b257c2a508e56a11fcdb07f6aa8028` was deployed to
Modal Workspace `unjuno`, environment `main`, app
`gpu-control-sites`. Modal built API images `im-4K01UJNs0MRcjkglisct1w` and
`im-Z63nygRSH8lcUALSM2Pfrn`; the deployed endpoint is
`https://unjuno--gpu-control-sites-control-api.us-east.modal.run`.

The first deploy attempt failed because Modal disallows a later build step after
a non-copy local source mount. The code now copies the bootstrap into the API
image (`copy=True`), with a regression assertion in `tests/test_modal_bootstrap.py`.
The complete Python suite passed **573 tests, 1 skipped**; `git diff --check`
passed. All six exact-head GitHub checks passed.

## Boundaries and remaining acceptance

- A read-only unauthenticated `GET /v1/health` returned HTTP 401. This confirms
  an auth gate on the route; it does not establish authenticated health or
  readiness.
- Imported source fingerprint: `53b5d84a82830a360f1b90bab6087e54723d9db21989ff3fb5440400f3991eec`.
  Sites still advertises `3bf90f4c3f99ab1bd9ad8f8a7714fbe63f4ccf8f308c729590e86f29c375d577`
  and digest `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
  The actual rebuilt OCI digest has not been verified/registered, so the
  deployed app and Site configuration are not accepted as a matching workload.
- The Modal UI showed a `$1` Workspace limit, `$0.10` usage this cycle, `$0`
  charges, `$1 of $30/mo` free credits, zero live containers and zero live
  Sandboxes. No Sandbox or inference was started.
- Sites admission remained `false`; no Site variables or secrets were changed.

## Credential cleanup record

The user authorized a one-hour Workspace token for the `main` deploy, with
immediate revocation afterward. During the initial UI token creation, its value
appeared in tool output; it was not used and was immediately revoked. A second
token was used for the approved deploy. The CLI-created temporary config had
mode `0644`; after deployment, the token was revoked, Modal's token inventory
showed zero API tokens, and the temporary config directory was deleted. No
token value is recorded here or retained. This incident should remain visible
for review; do not claim the secret was never exposed to tool output.
