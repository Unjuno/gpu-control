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

These checks are local. CI under its pinned uv `0.10.0` and an independent
security review of this exact patch remain pending. This change does not alter
Sites deployment, provider configuration, RunPod admission, or paid-execution
policy.
