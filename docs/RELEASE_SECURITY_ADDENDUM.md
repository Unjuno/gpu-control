# Release audit security addendum — 2026-09-08

Read with `RELEASE_AUDIT_2026-09-08.md` and `INDEPENDENT_ACCEPTANCE.md`.

## A10: known vulnerable development dependency

The new advisory gate on candidate `c653e6351caaddc6b2b7713316587d6b04187a11`
found `pytest==8.4.2` affected by `CVE-2025-71176` / `GHSA-6w46-j5rx-g56g`
(`PYSEC-2026-1845`). This is a development/test dependency, not the installed
runtime-only CLI dependency. The finding concerns insecure temporary directories
on UNIX; it is not evidence that a GPU account or credential was compromised.

Evidence: Package check run `34170175876`, job `101888833887`, artifact
`10035443124`, file `audit/dependency-audit.json`. Artifact ZIP SHA-256:
`1cdfd090b9a1cf4ba918ce570ea91410ea6ae3fa38616a09718c631e6b0ebadf`.

Pytest's official 9.0.3 release (2026-04-07) records the fix. The reviewed patch
raises the dev requirement to `pytest>=9.0.3,<10` and locks pytest 9.0.3. No runtime
dependency changes and no vulnerability-ignore entry are introduced. Distribution
URLs, sizes, hashes, and dependency metadata are taken from the exact PyPI 9.0.3
release. CI must validate `uv sync --locked` and the downloaded hashes before tests.

Primary sources:
- https://github.com/pytest-dev/pytest/releases/tag/9.0.3
- https://pypi.org/pypi/pytest/9.0.3/json
- https://github.com/advisories/GHSA-6w46-j5rx-g56g

## Results before the dependency update

CI run `34170175917` passed Python 3.11, 3.12, 3.13 and the trusted reference
container. Package run `34170175876` passed checkout tests (527 passed, 1 skipped),
build, standalone installed-wheel acceptance, extracted-sdist tests (527 passed,
1 skipped), sdist wheel rebuild, and selected Ruff checks. It correctly failed at
the dependency advisory gate. Those results are historical, not a final clean
security assertion for a newer commit.

The final reviewed head requires a fresh green CI matrix and Package check after
the pytest update, including a zero-known-vulnerability advisory result for the
examined environment. Record their run IDs and tested merge SHA in the PR review;
never reuse an older run as proof for changed files. A clean advisory result is
bounded by its date, advisory database, and dependency scope; it is not proof of
zero vulnerabilities. Windows-only and build/audit-tool dependencies are not all
covered by the Linux runtime/dev advisory export.

## Release boundary remains unchanged

No main merge, release publication, provider call, provider secret, paid workflow,
GPU allocation, or persistent-volume action is authorized or performed here. The
live GPU product remains NO-GO. The offline distribution remains a release
candidate pending final exact-commit checks and independent acceptance.
