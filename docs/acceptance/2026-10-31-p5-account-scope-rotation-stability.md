# P5 RunPod account scope stability across credential rotation — 2026-10-31

## Change

RunPod lease scope now derives from `GATEWAY_RUNPOD_ACCOUNT_SCOPE_ID`, a
stable, operator-managed identifier, and the shared HMAC key. The provider API
key remains necessary for adapter authentication, but is no longer part of
lease identity. Workers using old and new API keys for one account therefore
reserve the same account lease row during a rolling credential rotation.

The scope ID is omitted from `Settings` representations. Missing scope ID,
provider credential, or HMAC key fails closed before lease reservation.

## Verification

- Focused command:
  `cd gateway && ./.venv/bin/python -m pytest -q -o addopts= tests/test_provider_account_scope.py tests/test_experiment_api.py -k 'provider_account_scope or runpod_candidate'`
  -> **10 passed, 43 deselected**.
- Full Gateway command:
  `cd gateway && ./.venv/bin/python -m pytest -q -o addopts=`
  -> **512 passed, 16 skipped**, one existing Starlette deprecation warning.
- `git diff --check` passed.
- `policies/repository-state.yaml` remains `mode: parked`; live RunPod and paid
  execution flags remain false.

## Source hashes

- `gateway/gpu_gateway/provider_account_scope.py`:
  `915a60f500665e62b6d18379772341a2ccbd5be15c6e36b3acb33264c63a901e`
- `gateway/gpu_gateway/config.py`:
  `2c24578951cfab3f3732d0e17a5801857888ec304b3325e7a7be80c767785d9f`
- `gateway/gpu_gateway/worker.py`:
  `c8dfd76281b694a54d3424739a269c1be2232ea4b9e112b479403be6d0a4e6d5`
- `gateway/tests/test_provider_account_scope.py`:
  `5e29a7e59ee026bcd3686498bb921994aea409326a69003bdaafeb1a0cec2578`
- `gateway/tests/test_experiment_api.py`:
  `de13ec4811c90fdd2015606b6ee269d3a78e93946bcac766f6b71d2091923af6`

## Limits

These tests cover local/fake Worker dispatch. They do not prove production
secret distribution, cross-host configuration consistency, or live RunPod
allocation and recovery. The repository remains parked and no provider or paid
execution occurred.
