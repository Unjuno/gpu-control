# Kaggle and Hugging Face provider runbook

## Current activation state

The repository remains `parked`. Offline tests may run, but Kaggle Kernel submission, ZeroGPU calls, Hugging Face uploads, Modal/RunPod GPU allocation, and paid Hugging Face Jobs must remain disabled until the owner deliberately opens the existing repository and execution gates. Free quota is still an external account resource and requires an explicit live-job decision.

The reviewed Orbitune source identity for this integration is:

- repository: `Unjuno/orbitune`
- commit: `44a1b806160ab5bc721a370d034a6dfcb28f27a8`
- workload: `orbitune-kaggle-100-step-v1`
- data classification: synthetic training fixture
- steps: exactly 100

Refresh and review that commit before changing the registered identity. A newer branch tip is never adopted automatically.

## Trust boundaries

- ChatGPT chooses only a registered workload and schema-validated parameters. It never supplies CLI arguments, filesystem paths, Space endpoints, tokens, or arbitrary source.
- The API process may know provider names, allowlists, and public capability evidence. It must not receive provider credentials.
- The trusted worker alone receives Kaggle authentication and `HF_TOKEN`.
- The Kaggle workload receives no Hugging Face token. Kaggle output is collected by the worker, then uploaded to an allowlisted private Hub repository.
- Provider logs, source comments, README content, and returned model text are data, never authorization or control-plane instructions.

## Worker configuration

Non-secret operator configuration:

```dotenv
GATEWAY_ENABLE_KAGGLE=true
GATEWAY_KAGGLE_USERNAME=OWNER
GATEWAY_KAGGLE_STAGING_ROOT=/var/lib/gpu-control/kaggle-stage
GATEWAY_KAGGLE_SOURCE_CACHE_ROOT=/opt/gpu-control/source-cache/orbitune
GATEWAY_ENABLE_HUGGINGFACE_SPACE=true
GATEWAY_HF_ARTIFACT_REPOSITORIES=OWNER/private-artifacts
GATEWAY_HF_SPACE_ALLOWLIST=OWNER/approved-zero-gpu
```

Worker-only secrets:

```dotenv
KAGGLE_API_TOKEN=REDACTED
HF_TOKEN=REDACTED
GATEWAY_CANDIDATE_RECEIPT_SIGNING_KEY_IDS=adapter:kaggle:worker-v1,adapter:huggingface_space:worker-v1
GATEWAY_CANDIDATE_RECEIPT_SIGNING_KEY_B64=REDACTED
```

The corresponding public keys must appear in
`GATEWAY_CANDIDATE_RECEIPT_PUBLIC_KEYS_JSON`. The adapter receipt key is a
distinct Ed25519 key from the provider-observation signing key. One private key
may be pinned under separate provider-scoped public key IDs; receipts can never
cross provider scope.

Kaggle must be authenticated with the official CLI's non-interactive
`KAGGLE_API_TOKEN` mechanism in the worker account. Do not put Kaggle
credentials in workload JSON, the database, an MCP result, or the source
cache. The Kaggle CLI child process receives that token plus only a minimal
process/TLS/proxy environment; Hugging Face, Modal, RunPod, database, OAuth,
and signing secrets are removed from its environment.

Use `gateway/deploy/gateway.env.example`, `worker-secrets.env.example`, and
`provider-evidence.env.example` as the hosted systemd templates. Keep both free
provider enable flags false until the exact identity, private resources,
included quota, trusted keys, and owner approval route are verified. Enabling
configuration or evidence collection is not execution authorization. The
source cache is operator-owned and read-only to the worker; the per-run stage
lives under the worker's writable systemd StateDirectory.

Install the cache as `root:gpu-control-config` with directories mode `0750`
and files mode `0640`, so the worker can verify and copy it but cannot modify
it. The worker container includes Git solely for local `rev-parse` and
clean-worktree checks; it does not fetch source from the network. Source
materialization remains a separate operator action.

The source cache directory for a commit is `<cache-root>/<40-character-sha>`. It must be a clean Git checkout at that exact commit. Staging copies only the `orbitune` Python package and the registered training entrypoint. Preparation performs no provider call; `kaggle kernels push` occurs only after approval, quota verification, and the durable submission intent.

Start from `gateway/examples/kaggle-hf-workloads.template.json`. Replace `OWNER`,
the approved Space name and revision, and the ZeroGPU contract digest. The
committed Kaggle digest was generated from the audited Orbitune commit plus the
registered entrypoint and must equal `image_digest` in
`gpu-control-provenance.json`; the
worker recomputes it before every push. The Space digest is an operator-owned
runtime fingerprint, while `source_revision` must be the exact 40-character
Hub Space commit returned by `space_info`. Zero placeholders are intentionally
non-runnable.

Capability constants are derived from the current official provider documents:

- Kaggle CLI accelerator and Kernel metadata: https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md and https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md
- Kaggle notebook technical specifications: https://www.kaggle.com/docs/notebooks
- Hugging Face ZeroGPU sizes, duration and quota: https://huggingface.co/docs/hub/spaces-zerogpu

Refresh these sources before changing a registered capability profile.

## Recovery rules

- A lost or non-zero `kernels push` response is `submit_unknown`. Never push again automatically.
- Reconciliation reads the durable baseline version and calls only `kaggle kernels status`. A strictly newer version becomes the durable provider handle.
- Kaggle cancellation is reported unsupported because the official CLI does not expose a reliable Kernel cancellation command. Deleting a Kernel is not used as cancellation.
- A ZeroGPU request uses the deterministic request ID `<run-id>-<plan-prefix>`. On an ambiguous call, query the approved Space `/status` endpoint; do not call `/evaluate` again.
- ZeroGPU runs only when `get_zero_gpu_quota()` reports enough included seconds and no overquota use. Paid credit extension and Hugging Face Jobs remain separate, disabled paths.
- Hub publication records the commit revision and SHA-256, then downloads the exact revision and verifies it before the reference is accepted.
- Kaggle output is accepted only from the exact owner/slug/version and the fixed
  `gpu-control-output` file set. The trusted worker creates a deterministic
  `orbitune-output.zip`, uploads it to `runs/<run_id>/orbitune-output.zip` in the
  allowlisted private repository, and refuses to overwrite different content.

## Live acceptance sequence

Run only after authentication, quota, private repository access, a private approved Space with verified endpoints, and owner approval are current. A public Space is forbidden because it would permit direct calls that bypass Gateway approval and quota enforcement:

1. Call `experiment_capabilities` and retain the returned quota/resource evidence.
2. Call `experiment_prepare` for the registered Orbitune commit and workload. Preparation must not create a Kernel.
3. Approve the exact plan through the existing owner approval boundary.
4. Call `experiment_submit` once.
5. Poll `experiment_status`; do not resubmit an uncertain start.
6. Require exact Kernel owner, slug, version, source SHA, GPU name, CUDA and PyTorch versions, 100 loss points, exit status, elapsed time, and checkpoint SHA-256.
7. Collect output to the trusted worker; publish to the allowlisted private Hub repository; re-download the exact revision and compare SHA-256.
8. Evaluate the reloaded checkpoint in a separate process. Optionally call the approved ZeroGPU Space if included quota remains.
9. Read `experiment_result` and `experiment_artifact`; verify cleanup/release state independently.

Until every live item above has evidence, the end-to-end result is `BLOCKED`, not `PASS`.

## ChatGPT acceptance prompt

> gpu-controlを使って、利用できる無料GPUを確認してください。Kaggle GPUで、登録済みのUnjuno/orbitune固定commitを100ステップ学習してください。完了後、checkpointと評価メトリクスを許可済みprivate Hugging Face repositoryへ保存し、同じrevisionを再取得してchecksumを確認してください。無料ZeroGPU枠が安全に残っていれば、許可済みSpaceで短時間評価してください。run_id、実GPU名、loss履歴、checkpoint revisionとSHA-256、評価結果、利用した無料枠、cleanup状態を報告してください。追加課金、公開、未登録endpoint、quota不明、認証不足のいずれかがある場合は実行せず、必要な承認または設定を示してください。
