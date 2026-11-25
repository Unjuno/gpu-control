# P5 provider account scope key configuration — 2026-10-31

## Change

`Settings` can read `GATEWAY_PROVIDER_ACCOUNT_SCOPE_HMAC_KEY_B64` as a
dedicated operator-held key for deriving stable opaque provider account scopes.
It strictly decodes Base64, requires 32-4096 decoded bytes, and hides the
configured value from the settings representation. An unset value stays
`None`, so existing deployments do not silently acquire a fabricated scope
key.

## Verification

- TDD red: the focused test failed because the setting/property did not exist;
  malformed and undersized values were also accepted.
- TDD green: `cd gateway && ./.venv/bin/python -m pytest -q -o addopts= tests/test_provider_account_scope.py`
  -> **7 passed**, one existing Starlette deprecation warning.
- The tested environment value decodes to 42 bytes. Invalid Base64 and a
  decoded 6-byte key fail configuration validation.

## Limits

This only supplies configuration; Worker and the RunPod adapter do not yet
derive scopes or reserve leases with it. Key distribution, stable rotation
across active allocations, PostgreSQL and provider lifecycle behavior remain
unaccepted. RunPod remains disabled, repository mode remains `parked`, and no
provider call or paid execution occurred.
