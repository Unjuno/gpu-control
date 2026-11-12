# P3 package and CI candidate suite — 2026-10-31

Status: **PASS for local candidate-source suite and wheel contents only. GitHub CI, review, deployment, ChatGPT and target-host acceptance remain open.**

## Candidate and image

- Candidate source: `cccfcb8c62e0bbfd14cdecdbc907ef1f4b2beb59`, proposed range
  `d794c13..cccfcb8`.
- A detached worktree at this exact source built the CPU smoke image from its
  own Dockerfile, with matching OCI repository and revision labels. Image
  digest: `sha256:c135edc8461614a8ee5c36410ef3e438f5604ff8ec94735ee4ddf87202c85733`
  (`linux/arm64`). The image remains local and was not pushed.

## Local checks

- Full Gateway suite with disposable pinned PostgreSQL 16: **274 passed, 2
  optional skips**. Skips are the optional PyTorch bridge and Modal backend;
  one existing Starlette deprecation warning remained.
- Full Core suite: **517 passed, 1 Python-version-specific skip**.
- Built `gpu_control_gateway-0.1.0-py3-none-any.whl` from the candidate's own
  detached worktree. Inspected archive contains 23 `gpu_gateway` Python
  modules and four packaged UI/WebMCP assets. Wheel SHA-256:
  `a173430733f32f88e33833d938a9a385778d6d08d3722ce42586751f7fc43f7a`.

## Scope

The disposable worktree and database were removed. The existing primary dirty
worktree, branch, and refs were preserved. These results are local candidate
evidence only; they do not establish GitHub CI/review, hosted deployment,
ChatGPT OAuth/tool/run acceptance, target-host operations, or real GPU use.
Keep `policies/repository-state.yaml` at `mode: parked`.
