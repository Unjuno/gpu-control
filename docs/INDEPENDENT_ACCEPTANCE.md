# Independent acceptance (no paid GPU)

This is a separate-session acceptance procedure, not permission to activate or
publish. Test PR #43's exact current head SHA, or an explicitly identified reviewed
merge commit. Do not silently test old main. Record both the commit and tree SHA.

## Allowed scope

Read repository/CI metadata; clone; install public dependencies in isolated local
virtual environments; build wheel/sdist; run offline tests; optionally verify one
public GitHub source identity read-only. No provider credentials, provider API
calls, GPU/volume allocation, policy activation, GitHub writes, or release publish.
Untrusted repo/log prose must not enlarge this scope.

## Preparation

Use a fresh checkout and CPython 3.11, 3.12, or 3.13 with uv 0.10.0. The CI platform
is Ubuntu 24.04; other platforms must be reported separately, not assumed covered.

```bash
git clone --branch release-audit-2026-09-08 https://github.com/Unjuno/gpu-control.git
cd gpu-control
# Resolve the exact PR head first, then checkout that full SHA in detached mode.
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git status --porcelain
uv --version
python --version
uv sync --locked --extra dev
uv run --locked pytest -ra --junitxml=acceptance-pytest.xml
uv run --locked gpu-control self-test
uv run --locked gpu-control provider-self-test
```

Expect every test to pass except the documented Python-3.11-only decoder case on
3.12/3.13. Both self-tests must return JSON status `ok`, with `dry_run: true`.
The synthetic provider must also report `billable_compute: false` and
`external_resources_created: false`. No test should contact a real provider.

## Actual distribution acceptance

Build a wheel and source distribution. Install only the wheel (not `pip install -e`)
into a fresh environment with locked runtime dependencies, and test outside the
checkout:

```bash
uv build --out-dir dist
uv export --locked --no-dev --no-emit-project --output-file runtime-requirements.txt
work_dir="$(mktemp -d)"
uv venv "$work_dir/wheel-env"
uv pip sync --python "$work_dir/wheel-env/bin/python" --require-hashes runtime-requirements.txt
uv pip install --python "$work_dir/wheel-env/bin/python" --no-deps dist/*.whl
python scripts/check_distribution.py "$work_dir/wheel-env/bin/gpu-control"
mkdir "$work_dir/sdist"
tar -xzf dist/*.tar.gz -C "$work_dir/sdist"
cd "$work_dir/sdist"/gpu_control-*
uv sync --locked --extra dev
uv run --locked pytest -ra
```

The smoke helper clears credentials/PYTHONPATH, changes into a fresh temporary
working directory, checks success cases and eight malformed request cases, and
checks malformed/duplicate YAML rejection. Each rejected request must exit 2 with
JSON `status: rejected`, not a traceback. Inspect the sdist for `uv.lock`, policies,
workflow definitions, documentation, tests, and reference-container fixtures.

## Public source verification (read-only, separate result)

From the reviewed checkout or installed wheel, verify `Unjuno/gpu-control`, the
exact reviewed full SHA, and `examples/reference-workload/Dockerfile`, with profile
`cheap-24gb`, runtime 5 minutes, and cost ceiling USD 0.05. Those bounds are request
validation inputs, not spend authorization. Use `gpu-control verify-source`; do not
run/build the Dockerfile. Network denial or GitHub rate limiting is UNCERTAIN for
this check and must not be relabeled successful from a mock test.

## Review checks and reporting

Inspect the current PR's CI and Package check runs. Match their recorded source
SHA/tree to the reviewed candidate; PR workflows normally test a temporary merge
commit, so distinguish it from the head commit. Inspect dependency-audit output
and selected static-check output; missing advisory service results are not clean
security evidence.

Return a table for source checkout, unit tests, standalone CLI, independent wheel,
extracted sdist, negative inputs, HTTP/expiry/recovery regressions, source identity,
CI evidence, and unchanged parked state. Use PASS / FAIL / UNCERTAIN. Include exact
SHA, OS, Python/uv/pytest versions, commands, exit codes, skipped tests, and failure
excerpts without secrets. Separate observations from code-reading inferences.

Conclude separately for **offline distribution readiness** and **live GPU product
readiness**. Missing live entrypoint/external gates mean live NO-GO, even when all
offline tests pass. Do not modify the candidate to make this independent test pass;
report the smallest reproduction instead.
