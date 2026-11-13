# Reproducible PEP 517 build dependencies — 2026-11-13

## Change

- Pinned the project build backend to `setuptools==84.2.1` and
  `wheel==0.48.0` in `pyproject.toml` and added matching uv build constraints.
- Added `build-constraints.txt` with SHA-256 hashes for the exact PyPI wheels
  for `packaging==26.3`, `setuptools==84.2.1`, and `wheel==0.48.0`. `packaging`
  is constrained because the selected setuptools backend requests it as a
  dynamic build dependency.
- CI now builds the source and wheel with `uv build --build-constraints
  build-constraints.txt --require-hashes` before syncing the project.

## Local verification

- `uv lock --offline` — resolved 35 locked packages and recorded the exact build
  constraints in `uv.lock`.
- `uv build --build-constraints build-constraints.txt --require-hashes` — built
  the source distribution and wheel successfully with the selected dependency
  hashes. Setuptools emitted an existing deprecation warning for the
  `project.license` table; the build succeeded.
- `uv sync --locked --extra dev --offline` — passed.
- `uv run --locked --offline pytest -q` — **573 passed, 1 skipped**.

The local checks passed. CI under its pinned uv `0.10.0` and a Codex Security
diff review of this exact patch passed at code commit
`cc076b8157d467e985f0ef0f550b8c42bc2bf85f`:

- GitHub CI run `43381726975`: Python 3.11, 3.12, 3.13, Sites Worker and D1
  contract, and Trusted reference container all passed.
- Project bridge tests run `43381726868` passed.
- Exact-range Codex Security diff scan `6d1a4697-bbd5-4526-83c5-f2f78c3c1ca6`
  reported zero findings across four reviewed surfaces.

The scan is limited to this build-tooling diff. It does not replace the
repository-wide P0 audit, and this change does not establish Sites deployment,
provider configuration, RunPod admission, or paid-execution acceptance.
