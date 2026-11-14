# Budget and local regression recheck — 2026-11-15 02:33 JST

## Current hosted state

- Modal Usage & Billing was read in the authenticated browser. It showed `$0.10`
  in credits used, `$0` in charges, and the Workspace usage limit at `$1`.
  This remains under the user's `$1` aggregate project-testing budget. No
  payment method or billing setting was changed.
- ChatGPT `experiment_capabilities` returned
  `CPU_WORKLOAD_ADMISSION_DISABLED`, `available=false`, with health deferred
  until exact-plan confirmation. Admission remains closed.
- Plan `ade7d8e5ce6a4961b16d847c393fd769` was prepared for TinyStories 15M,
  prompt `Once`, one token, seed `61112`, 30 seconds, CPU only, 1 core, and
  512 MiB. Its estimate was `$0.0013` for Sandbox CPU/memory, with a `$0.01`
  Sandbox-only ceiling; Modal control-function charges are separate. The plan
  was not confirmed or submitted. After its 10-minute confirmation window,
  Sites status returned `RUN_NOT_FOUND`.
- Existing latest Modal-origin run `e9330c5bb5454f42bb3dabe058091dc0` remains
  failed with `MODAL_WORKLOAD_EXIT_2`, cleanup confirmed, and no result
  artifact. No fresh provider health request or Sandbox was initiated.

## Local regression checks

- `node --test --test-name-pattern='retired Runner routes stay closed even when a legacy bearer is supplied' sites/gpu-control-sites/worker/index.test.js`
  passed **1/1**. The Worker rejects the retired Runner route even when a legacy
  bearer value is supplied in the test environment.
- `PYTHONPATH=src python3 -m pytest tests/test_modal_bootstrap.py -q` passed
  **7/7**. This checks the fixed Sandbox bootstrap and bounded diagnostic map
  locally; it does not prove Modal's remote image, result transport, or cleanup.
- A tracked-source search found no active personal-host Keychain launcher or
  compute Runner implementation. Remaining code references are the workload's
  forbidden-secret environment list and a negative regression test. This is a
  scoped source check, not the requested repository-wide P0 audit.

## Exact-head CI and PR state

- PR #68 remains open and Draft, with no submitted independent review.
- For commit `8cb4ea87e9157272aa77391d467fbc078a1dfa87`, exact-head GitHub
  Actions completed successfully: Python 3.11, Python 3.12, Python 3.13,
  Trusted reference container, Sites Worker and D1 contract, and Project bridge
  tests. This passing CI does not replace the incomplete repository-wide P0
  Deep Scan or live provider acceptance.

### Follow-up: boundary-safe plan expiry assertion

- The subsequent docs commit `cc1ee922` found a timing-sensitive test assertion:
  the plan confirmation route correctly used the earlier plan expiry, but the
  test assumed the full 300 seconds remained after the authenticated request
  crossed a Unix-second boundary (observed lifetime: 299 seconds).
- The test now verifies `authorization.expires_at === plan.expires_at` and that
  authorization remains valid at the recorded instant. The full Sites Worker
  suite passed **43/43** locally.
- Code commit `9a8adffa8df1509b05d994a23052a7bd760646bc` passed exact-head CI:
  Python 3.11, 3.12, 3.13, Trusted reference container, and Sites Worker/D1
  contract, plus the Project bridge tests workflow. PR #68 remains Draft and
  has no independent review.

## Security audit blocker

The repository-wide Codex Deep Scan did not start. The exact coordinator error
was: `Deep Scan cannot safely start a read-only worker: the parent must provide
a managed filesystem permission profile.` No scan artifacts, complete review,
or security clearance were produced. This session cannot supply that profile.

## Next gates

1. Resume the P0 Deep Scan from a session that provides the managed read-only
   filesystem profile.
2. Reconcile and health-check the deployed Modal API and image identity. Keep
   admission closed until provider health and effective Sandbox CPU/memory
   limits are verified.
3. After those gates, prepare a fresh exact plan, obtain owner confirmation,
   and use the remaining aggregate budget for a real ChatGPT-to-Modal CPU run.
   Capture result provenance, cleanup, and post-run Usage & Billing evidence.
4. Keep RunPod/GPU and broader paid execution parked until their own Site route,
   authorization, trusted completion evidence, recovery, cleanup, and spend
   checks pass.
