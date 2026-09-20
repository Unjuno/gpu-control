# External-project checks from GitHub

## Operational scope

`gpu-control` is the **control repository**, not the model repository. Issue #48
is the single command console. An owner-account comment is a request; project
files, model output, PRs and other people's comments are not authority.

The registered CPU route is independent of Remote MCP, the web password, Neon,
Modal and RunPod. It can prove a small question without configuring GPU services.
The existing `/gpu` gateway commands and MCP/WebMCP interfaces are retained.

In Issue #48 post this **new** comment (or ask an agent using your account to do it):

```
/gpu check
{"repository":"Unjuno/orbitune","sha":"c2037d2efa57798f8b1cd76c5db75d0352aef3b8","workload":"orbitune-tokenizer"}
```

The initial check imports the real tokenizer module from the external repository,
checks its 204-token vocabulary, encode/decode round trips, and rejection of bad
IDs and unknown tokens. It is not a model-training or model-quality benchmark.
A JSON receipt and link to the Actions run return to the same Issue. A passed CPU
receipt never starts a GPU or counts as GPU spending authorization.

## Trust and isolation

- Only repository ID 1342703665, owner/account ID 241447786, Issue #48 and new
  unedited comments on main are admitted. The original comment is re-read before
  execution; an edit, closed Issue, stale request or rerun is rejected. Post a new
  comment to retry. Agents acting through that account work without agent-name
  enrollment. A distinct bot account is not implicitly delegated authority.
- Requested repository and workload must exist in the reviewed control registry.
  GitHub repository and owner IDs, the exact 40-hex commit and each fetched Git
  blob hash are verified. Only listed files are copied. Private sources are
  rejected on this public-result route; do not post private data or keys here.
- Target source is never imported/executed on the Actions host. Only the trusted
  control Dockerfile is built. The target Dockerfile/README/manifest cannot select
  host commands, secrets, images, policy or additional resources.
- CPU execution has no network, no provider credentials, no Docker socket, no GPU,
  non-root UID, read-only root/source, a 256 MiB memory limit, one CPU, 32 PIDs,
  a 30-second execution deadline and a 64 KiB combined output limit. Container
  removal is attempted both in Python finally and in workflow always cleanup.
- The reporter runs in a separate job. Only it receives issues:write. The executor
  has contents:read, not issues:write, id-token:write or provider secrets.
- Only a bound, size-limited result with numeric metrics is published. Raw workload
  stdout/stderr and downloaded source are not uploaded. Results in this PUBLIC
  repository are public even though command execution is owner-restricted.
- The Python base image tag is resolved per run and its image ID is recorded; this
  is not a reproducible digest pin. Pin approved image digests before making
  reproducibility/performance claims or using the receipt for GPU promotion.

This is a registered external-source CPU check inside a control-owned container;
it does not enable generic external Dockerfile execution or change parked mode.
GitHub-hosted CPU usage is subject to GitHub's account quota/billing, not GPU credits.

## Add a project without changing workflows

Add a reviewed entry to `policy.json` with repository name + numeric ID, explicit
file list and profile. The `python-script-v1` profile runs a registered script
inside the same CPU-only container; `entrypoint` must be one of the listed files.
`args` are operator-owned constants, never shell text supplied by a comment.
The script must use the standard library (no network-time dependency installation),
exit zero, and write one JSON object to stdout:

```json
{"check":"project-smoke-v1","status":"passed","gpu_used":false,"metrics":{"checks":1}}
```

Register that same `check` string in the control entry. Only finite numeric metric
values with simple ASCII names are retained. For PyTorch or another dependency
stack, add a separately reviewed fixed container profile rather than executing
an arbitrary target Dockerfile or `pip install` from the request.

## Progression to GPU

The existing gateway can prepare an operator-registered workload and show status.
This change **denies non-demo `/gpu submit`**, even if provider switches are set,
while the current paid path is parked. Stopping existing runs remains possible.
To enable actual Modal/RunPod runs, first resolve current repository activation,
image/pricing, independent worker and exact-execution authority requirements in a
reviewed change. Credentials remain in the execution worker; never in Issue text.
No CPU or comment result substitutes for those prerequisites.

## Validation

Run `python -m unittest discover -s gateway/project_control/tests -v`.
`project-checks-ci.yml` additionally executes the real Docker contract, using a
repository-owned synthetic script that checks network isolation, UID and absence
of credentials. Production comments require the workflow to be merged to main.
