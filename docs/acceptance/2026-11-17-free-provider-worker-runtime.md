# Free-provider worker runtime rehearsal — 2026-11-17

Scope: local container and public-source staging only. No Kaggle API, Hugging
Face API, GPU, provider credential, paid resource, or live admission was used.

## Reproduced defects

The pre-fix `gpu-control-gateway-worker:local` image had two live-path defects:

1. Git was absent, so `stage_orbitune_checkout` could not verify the exact
   source commit or clean worktree.
2. `gateway/workloads` was absent from the image, so the registered Kaggle
   entrypoint could not be copied into a stage.

After those were fixed, starting `kaggle==2.2.5` exposed a third defect:
`ModuleNotFoundError: No module named 'six'`. `six==1.17.0` is now a direct,
pinned worker dependency.

## Post-fix evidence

The rebuilt worker image reported:

- Git `2.47.3`;
- Kaggle CLI `2.2.5`;
- importable `huggingface_hub` and `gradio_client`;
- both registered `orbitune-kaggle-100/train.py` and
  `orbitune-zero-gpu-eval/app.py` present.

The public `Unjuno/orbitune` repository was fetched at the exact registered
commit `44a1b806160ab5bc721a370d034a6dfcb28f27a8` into a disposable local
directory. The worker image then staged it as UID 10001 with:

- `--network none`;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- the source bind-mounted read-only.

The staging result identified exactly 100 synthetic-data steps and produced
`sha256:90c9c8dc008d1cfa9aa083f313276d68f171f00a38639f03ead3d8726ed0499b`,
which matches the registered Kaggle workload template. The disposable checkout
and output were moved to Trash after verification.

This proves local worker-image readiness and exact-source staging only. It does
not prove Kaggle authentication, quota, submission, GPU execution, private Hub
upload, ZeroGPU evaluation, hosted Gateway operation, ChatGPT retrieval, or
provider cleanup.
