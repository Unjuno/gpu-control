# Modal fixed CPU provider

This App serves one authenticated control API and starts only the registered
`tiny-stories-inference-v1` workload in a network-blocked Modal Sandbox. The
Modal Web Function is protected by a Workspace Proxy Token. The API accepts
only bounded parameters and a D1-bound run identity; the Sandbox receives no
Modal token, Sites token, bearer token, or provider credential.

`app.py` builds the workload image from the pinned Dockerfile and checks that
the copied inference program and C source match the previously registered
GitHub workload source. The API uses deterministic Sandbox names so an
ambiguous retry attaches to the original running or recently terminated
Sandbox instead of starting replacement compute. A Sandbox requests and is
hard-limited to 1 physical CPU core and 512 MiB, with blocked outbound
networking and at most 30 seconds of runtime. The resource tuple is included in
the workload image fingerprint. CPU usage at the limit is throttled; exceeding
the memory limit can OOM-terminate the Sandbox and fail the run.

## Deploy requirements

- Modal Python SDK 1.6.3. The fixed API uses the documented
  `Sandbox.create(cpu=(request, limit), memory=(request_mib, limit_mib))`
  resource tuple form; see the [Python Sandbox reference](https://modal.com/docs/sdk/py/latest/Sandbox).
- The API image installs the hash-locked dependency set in `requirements.txt`.
  Update top-level constraints in `requirements.in`, regenerate the lock with
  `uv pip compile --generate-hashes --output-file requirements.txt
  requirements.in`, then run the repository dependency audit before deploy.
- A Modal deploy credential kept outside the Site and repository.
- One Proxy Token with access only to the `main` Modal Environment, if the
  Workspace supports environment-scoped proxy tokens.
- Store the returned endpoint URL, Proxy Token ID, and secret only in the Sites
  runtime environment. Never pass them into workload parameters or its
  container.
- Leave provider admission disabled until the app is deployed, endpoint auth
  is checked, readiness matches the image fingerprint, and the current
  account's usage cap is confirmed.

The endpoint is deliberately not a general compute API. Do not add caller
selected commands, images, URLs, resource sizes, GPU requests, or secret names.
