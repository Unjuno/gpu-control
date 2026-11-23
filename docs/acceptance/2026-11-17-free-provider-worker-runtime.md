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

The initial staging result identified exactly 100 synthetic-data steps and
produced the then-registered digest
`sha256:90c9c8dc008d1cfa9aa083f313276d68f171f00a38639f03ead3d8726ed0499b`.
The disposable checkout and output were moved to Trash after verification.

This proves local worker-image readiness and exact-source staging only. It does
not prove Kaggle authentication, quota, submission, GPU execution, private Hub
upload, ZeroGPU evaluation, hosted Gateway operation, ChatGPT retrieval, or
provider cleanup.

## Official CLI contract check

The pinned CLI's local help confirmed that `kernels push` accepts both
`--accelerator` and `--timeout`, and that `quota` supports JSON. It also exposed
that `kernels status` does **not** support JSON, contrary to the earlier mock
contract. The backend now:

- uses the documented `machine_shape` metadata field;
- repeats the exact accelerator and runtime ceiling on the push command;
- gets latest-version and exact-version status through a narrow read-only
  bridge over the official Kaggle client package;
- parses a successful push's exact version and checks that exact version;
- never retries an ambiguous push; and
- accepts ambiguous-submit recovery only after downloading that candidate
  version and matching the exact script plus its private/no-network/no-source/
  no-custom-image GPU metadata; the candidate must be `baseline + 1`.

The pinned CLI source also established that quota JSON is a list with a GPU row
whose remaining value is formatted to two decimal hours. The parser now
handles that exact form, rejects duplicate/malformed GPU rows, and subtracts
the maximum half-unit rounding error before converting the value to seconds.

These checks still do not establish live authentication or provider behavior;
that remains part of the owner-authenticated acceptance phase.

## Single-file upload correction

Review of Kaggle CLI 2.2.5 showed that a script Kernel push uploads the
metadata-selected `code_file`; it does not make the adjacent `orbitune/`
directory available to the remote script. Therefore the earlier local stage
was not remotely runnable even though its digest was internally consistent.

The stage builder now packages every reviewed Orbitune file from the exact
commit into a deterministic ZIP, embeds it in `train.py`, verifies the embedded
SHA-256 before import, and keeps the Kernel network-disabled. The rendered
single script is 146,921 bytes. The corrected registered stage digest is
`sha256:3f764ee4d610edfbe6b07769538ffbae8413b9df47c05af783245d65c7c21bed`.
The acceptance test decodes the embedded archive and verifies canonical paths
including `orbitune/model.py` and `orbitune/tokenizer/vocab.py`.
