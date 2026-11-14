# Sites Version 35 native plan preparation — 2026-11-15

## Scope

This checkpoint verifies the non-billable portion of the ChatGPT-native exact
plan flow after Sites Version 35 publication. It does not claim provider health,
Sandbox creation, inference, result, artifact, or cleanup acceptance.

## Observed ChatGPT tool contract

- A fresh goal turn loaded the Version 35 `experiment_submit` schema.
- The submit tool now requires `approved_plan`, `plan_fingerprint`, and
  `run_id`. The exact plan contains workload, repository and commit, prompt,
  token limit, seed, runtime, estimated Sandbox cost, cost ceiling, CPU and
  memory limits, GPU prohibition, and the control-function cost caveat.
- The tool is described as a destructive write requiring ChatGPT confirmation.
  No separate Site/browser sign-in is part of this path.

## Read-only capability refresh

The authenticated owner capability call returned `status=ok` with:

- Modal configured and CPU admission enabled;
- exact plan confirmation and authorization storage ready;
- CPU request/limit of 1 physical core;
- memory request/limit of 512 MiB;
- maximum runtime of 30 seconds;
- estimated maximum Sandbox cost `$0.0013` and ceiling `$0.01`;
- Modal control-function cost excluded from that ceiling;
- registered fingerprint
  `8a786eb77ff845ed053ce939a4f4601705c01defb2b6fab7c1dd804ca04b09c5`.

Provider readiness remained deferred until an owner-confirmed submit. The
capability response is control-plane evidence and does not attest the running
Sandbox image or provider-side limits.

## Prepared plan

The owner-authenticated `experiment_prepare` call succeeded without a browser
login and created this bounded, unexecuted plan:

- run ID: `3c34de84e2b84282b722eaff8e00c18b`;
- plan fingerprint:
  `161fad185ef96a94e8914eea47ec40d81d265aa2183cfa40b3948d274e00ea8f`;
- workload: `tiny-stories-inference-v1`;
- source: `Unjuno/gpu-control` at
  `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`;
- prompt `Once`, one new token, seed `61115`;
- 30 seconds, CPU 1 physical core, 512 MiB, GPU prohibited;
- Sandbox estimate `$0.0013`, Sandbox ceiling `$0.01`, control-function cost
  excluded;
- authorization surface `chatgpt_mcp_write_confirmation`, one run, 600-second
  validity.

The user was away and could not perform the exact destructive-write
confirmation. `experiment_submit` was therefore not called. No provider health
request, Modal Sandbox, RunPod request, GPU allocation, or new provider spend
occurred. A later execution must prepare a fresh plan and obtain a new exact
confirmation; this expired plan is not reusable.

## Remaining acceptance

A fresh owner-confirmed plan must still complete through submit, provider
health, bounded inference, terminal status, verified R2 artifact digest,
confirmed cleanup, and post-run billing review. Only then can the current Modal
CPU vertical be accepted and recovery testing begin.
