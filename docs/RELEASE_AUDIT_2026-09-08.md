# Release audit — 2026-09-08

## Decision and scope

Baseline: `Unjuno/gpu-control@a96a24818a5f8bc03b479c35b5e3f957f08dbe04`.
Review branch: `release-audit-2026-09-08`; pull request: #43.

**Live GPU product: NO-GO. Offline validation/control-plane distribution: candidate,
subject to green final PR checks and independent acceptance.** Main has not been
merged, a GitHub/PyPI release has not been published, and no provider resource has
been allocated by this audit. A successful offline test is not paid-run authority.

This audit covers the tracked wrapper snapshot: public CLI, policy/input parsing,
source reader, plan/authorization interfaces, provider HTTP boundaries, RunPod
submission/reconciliation/recovery, completion/result contracts, workflows,
distribution contents, and user-facing documentation. It is not a formal proof of
all programs or a live audit of the separate Orbitune workload/provider account.

## Reproduced findings and changes

| ID | Severity / boundary | Baseline evidence | Change / regression coverage |
| --- | --- | --- | --- |
| A01 | High, future allocation | Occupancy read advances the clock past pricing/permit expiry; create still occurs. | Recheck both immediately before create, in v1 and legacy v2 paths. `test_release_regressions.py`. |
| A02 | High, HTTP credentials | A provider error can echo the supplied API key in message/detail. Default urllib redirects can forward credential-bearing requests. | Never echo HTTP error bodies; reject redirects in all default credential-bearing readers. Test real urllib redirect dispatch using a fake transport, no socket. `test_http_security.py`. |
| A03 | Medium, response boundary | Metadata/catalog HTTP responses are read without a size bound; non-finite timeout is accepted. | Bounded 1 MiB JSON reads, nesting limit, duplicate-key/non-finite/invalid-Unicode rejection, finite positive timeouts. |
| A04 | High, future cleanup | Reconstructing the allocating adapter after permit/price expiry prevents asynchronous recovery. | Explicit recovery-only mode, bound to one receipt plus independently trusted expected fingerprint. Historic evidence is checked at receipt submission time; allocation always denied in recovery mode. `test_runpod_recovery.py`. |
| A05 | High, future cleanup | A uniquely reconciled created Pod can fail price/occupancy checks without compensating termination. | Compensate only after candidate ID, execution name, and image agree; never delete an unrelated/inconsistent response. `test_runpod_reconciliation.py`, `test_runpod_recovery.py`. |
| A06 | Medium, public inputs | Floats/booleans can be converted to runtime/GPU integers; dot/empty path segments normalize silently; extreme cost escapes as Decimal error. | Strict integer types/ASCII digits; validate original bounded path; reject controls; convert extreme decimals into the public validation error. |
| A07 | Medium, policy parsing | Malformed YAML escapes the CLI error contract; duplicate keys overwrite safety limits. | Strict resource-policy loader, duplicate-key and schema-version checks, bounded text, positive exact-integer policy fields. |
| A08 | Release-blocking, sdist | New package CI fails: lockfile, policies, docs, agent/security files, workflows, and fixtures are absent from sdist. | Explicit `MANIFEST.in`; build and retest extracted sdist; install wheel into a separate environment outside the source checkout. |
| A09 | Medium, build/docs | Unbounded build backend requirement; deprecated license metadata; README/agent docs name obsolete source/API/completion contracts. | Pin build backend, SPDX license metadata, update selected source/v1/v3 descriptions and add documentation/state consistency tests. |

The recovery fingerprint is not a signature and not an identity provider. A future
trusted workflow must authenticate durable state and authorize recovery separately;
callers must never manufacture evidence merely to satisfy a constructor. The
low-level HTTP clients are not a sandbox and are not a substitute for the reviewed
entrypoint/credential boundary.

## Evidence

Initial diagnostic PR commit: `4abfbeccc4d48ee428b2963c00b29faacf3ab3a6`.
Its tested merge snapshot was `98258cb231e8d4392e4fe0c15fc272105e11e7fd`, consisting
of the baseline plus the initial package-check workflow.

- GitHub package run `34168152277`, job `101883199818`: Ubuntu 24.04.4,
  CPython 3.13.15, uv 0.10.0, pytest 8.4.2, PyYAML 6.0.3.
- Baseline suite: **452 passed, 1 skipped**. Isolated installed-wheel self-tests
  and import checks passed. The new source-distribution completeness check failed.
- Baseline artifact `10034830668`: ZIP SHA-256
  `82958b458cd2cca0e36695cea671e10fbc7fe99622b5bff44de7d1c56e6930ce`.
- New adversarial regression probes before fixes: **31 failed, 1 passed**.
- Supplemental local repaired suite: **527 passed, 1 skipped**, CPython 3.13.5,
  pytest 9.0.2, PyYAML 6.0.3. This local pytest version is outside the project's
  declared dev range; the locked GitHub matrix, not this supplemental run, is the
  release authority. Final supported-version results belong to the exact PR head's
  CI and package-check runs and their JUnit artifacts.
- The existing skipped case is a real JSON-decoder recursion reproducer specific
  to Python 3.11; it runs on 3.11 and is intentionally skipped on 3.12/3.13.
- Unit/contract tests now deny real socket connections and DNS resolution.

The package workflow records source SHA, tool versions, JUnit, wheel acceptance,
build output, distributions, selected static checks, and a dated dependency-advisory
result. Static checks select E9/F821/F822/F823 only; this is not full lint, type
checking, or an independent security certification. Advisory matching cannot prove
absence of undisclosed vulnerabilities. Audit-tool transient dependencies are not
part of the project's runtime lockfile.

## Remaining live-release blockers

| Area | Required evidence before live release |
| --- | --- |
| GitHub authority | Main protection and required checks actually enforced; owner-only protected paid environment; correct secret scopes. Main was observed unprotected. Environment/secret settings were not independently verified and must not be described as confirmed absent. |
| Trusted evidence production | Authenticated current DecisionRecord/human intent, protected control-plane SHA, image build/publish provenance, and current provider evidence. Dataclass shape checks and synthetic fixtures are not these producers. |
| Real provider/account | Current price and exact-DC stock, occupancy, immutable registry digest, existing supported Network Volume, S3 credentials and actual completion/cleanup behavior. No live provider call was made. |
| Crash/cancellation safety | Durable write-ahead allocation intent, independently recoverable state, single-use execution/lease semantics, and a tested cancellation/timeout/reconciliation supervisor. The in-memory controller plus serializers are not a deployed durable scheduler. |
| Cost accounting | A real total-cost model including persistent storage and cleanup delay, and tested enforcement. The current compute-rate-times-runtime estimate is not a guarantee on the entire provider invoice. |
| Launch and final acceptance | Protected end-to-end entrypoint, isolated workload build/run, one explicitly authorized bounded live canary, authenticated outputs, independent resource-release confirmation, and workload-specific final acceptance. |

Additional hardening before exposing persisted-state inputs to untrusted producers:
bounded decoding across all legacy plan/lifecycle/result restoration paths, strict
schema type consistency, and equivalent duplicate-key rejection for the legacy
paid/result policy loaders. These paths were reviewed but not broadly redesigned
in this patch. Generic hostile external Dockerfiles remain disabled.

No persistent volume is created/resized/deleted by this audit. Removing a Pod does
not imply that all persistent provider charges or artifacts have disappeared.

## Acceptance model

**H:** An independent fresh Linux environment can reproduce the offline CLI,
negative-input behavior, and wheel/sdist tests for the exact reviewed commit,
without provider credentials or GPU allocation.

**T:** Follow `INDEPENDENT_ACCEPTANCE.md`; run the locked matrix, both standalone
self-tests, installed-wheel acceptance, extracted-sdist pytest, selected static
checks, and the dependency advisory check. A separate public-source verification
is read-only; no provider request is permitted. Stop on a reproducible discrepancy.

**D:** Offline PASS requires every mandatory local/package check to pass. A
reproducible defect is FAIL. Missing network, build prerequisites, or incomplete
external evidence is UNCERTAIN for the affected check, never a fabricated PASS.
Live remains NO-GO until every external gate and bounded live acceptance is proven.

**C:** Checkout-only success may conceal missing package data; mocks may diverge
from the provider; a fresh permit may expire during a network probe; a restart may
lose cleanup authority; result authentication may not prove workload correctness.

**U:** Untested OS/Python variants, runner/provider changes, network races, account
state, and incomplete external authority. No statistical confidence interval is
claimed for deterministic tests or for unmeasured live failure probabilities.
