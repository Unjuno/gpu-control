# Current operations: ChatGPT Sites + D1

The supported ChatGPT control plane is the owner-private Sites MCP Worker at
`https://gpu-control-sites.unjuno.chatgpt.site`. Its product records are stored
in the Sites-provisioned D1 database. The current free CPU Runner is a separate
host process and executes only the exact registered Linux workload image. The
Site Worker does not execute containers or accept caller-selected code, images,
or provider settings.

## Verified now

- ChatGPT can discover and call the private Site's experiment tools.
- One fixed-image CPU checksum smoke completed through ChatGPT → Sites → D1 →
  Runner → D1 → ChatGPT; result retrieval and container cleanup were confirmed.
- One TinyStories 15M inference completed through the same ChatGPT → Sites →
  D1 → Runner → D1 → ChatGPT path. A 24-token result was retrieved, identity
  and checksum validation passed, and container cleanup was confirmed.
- Two more inferences completed after enabling the Site's R2 binding and
  append-only D1 artifact metadata migration. ChatGPT read complete 988-byte and
  991-byte result artifacts; the Worker verified owner/run identity and SHA-256
  before returning each chunk. They used 12 tokens each, took 249 ms and 268 ms,
  and had `$0.00` ceilings.
- Three additional provenance-valid inferences have completed, including one
  post-deploy run. ChatGPT retrieved three complete R2 artifacts and verified
  their recorded SHA-256 values; every accepted run confirmed container cleanup
  and a `$0.00` ceiling. The complete run inventory is in `docs/RELEASE_MATRIX.md`.
- A seventh provenance-valid run (`5447466fe7f9413980d2b47a2b079289`) was
  retrieved through ChatGPT. It generated four tokens in 150 ms, passed identity
  and sandbox checks, and confirmed cleanup at `$0.00`.
- An eighth live recheck (`1fdfe901fda14798a42e33e492edd538`) was prepared,
  submitted, polled, and retrieved through ChatGPT. It generated four tokens in
  155 ms, passed identity/sandbox checks, reported `gpu_used=false`, and
  confirmed cleanup at `$0.00`.
- A fresh run (`a1cdf7e9516b4a00802b6b606f228b08`) completed through the
  currently deployed Sites Version 15. It generated 8 tokens in 227 ms,
  passed registered source/model/parameter and container-isolation checks,
  reported `gpu_used=false`, and confirmed cleanup at `$0.00`. ChatGPT retrieved
  the complete 979-byte R2 result artifact and the Site verified its SHA-256.
- Repeating the same submission returns the existing run instead of starting
  another container.
- CPU admission is limited to one in-flight run and 30 seconds. The workload
  reports `gpu_used=false`; paid provider execution remains parked.
- A live cancellation probe (`0a61c2b307f14dfbb94d9791ff7d7139`) was submitted
  and cancelled while running. D1 reported `cancelled` with
  `failure_code=caller_cancelled`, `cleanup_state=confirmed`, and no pending
  cancellation. A follow-up capabilities read showed the Runner ready and the
  free CPU admission slot available again. This proves the explicit cancellation
  path for one bounded run; it does not prove forced-process-death recovery.

These checks prove repeated provenance-valid bounded CPU inferences, five
complete R2 artifact retrievals, and one live cancellation/cleanup path through
ChatGPT. They do not prove general model quality, GPU execution, forced Runner
restart or process-death recovery, cross-owner isolation, long-term artifact
retention, or backup/restore.

The currently deployed Site is Version 15, deployment
`appgdep_6af5169fa69c8191b4dca5bb77272c84`, from Sites source commit
`e3cfaf71c5f084c6a6ab40adbae8e189327197ad`; it reports MCP ready and served the
new inference above. Version 13 introduced a D1 protocol-version check so
legacy Runners fail closed. The live macOS LaunchAgent is running with login
Keychain credentials; its `run.py` and Keychain launcher hashes match the
published source, and plist/runtime files have mode `0600`. Static security
review found no actionable issue in the reviewed diff. It did not exercise
restart, cancellation, Keychain ACL, or credential rotation.

## Operating boundaries

- Keep the Site owner-private. Sites authenticates MCP callers; each tool must
  still enforce persisted owner checks.
- Keep provider credentials out of the Site source, MCP arguments, logs, and
  workload container. Store runtime secrets only through the Sites secret
  controls and the Runner host's protected secret mechanism.
- Keep paid execution parked until its separate approval, price, quota,
  authentication, cleanup, and recovery gates pass.
- Do not bring the archived FastAPI/PostgreSQL, Vercel, or Neon stack back into
  the product path. Historical runbook: `archive/OPERATIONS-legacy-postgresql.md`.
- Vercel is not a rollback dependency for Sites. Retire its legacy project
  after checking DNS, GitHub hooks/status requirements, and user workflows for
  remaining references. Do not direct product traffic back to that deployment.
- Do not delete the existing Neon project until its auth/run records are
  classified and any retained data has a verified export or is explicitly
  recorded as disposable. The live control plane uses D1.

## macOS Runner secret and service management

The deployed macOS LaunchAgent reads both Runner credentials from the user's
login Keychain at launch and keeps them in process memory. Its plist contains
only the fixed Site URL, registered source/image identity, and polling
settings. The plist is written atomically with mode `0600`; a missing Keychain
entry fails closed. The installed service and Keychain items are present, and
the running source hashes match the published Version 15 source.

To provision or operate it after admission is closed and all runs are terminal:

1. Generate a fresh high-entropy Runner bearer, configure it as the masked
   `RUNNER_BEARER_TOKEN` Sites secret, and store that same value in the login
   Keychain under service `com.unjuno.gpu-control.runner`, account
   `runner-bearer`. Also store the Sites service-access credential in account
   `sites-service`. Use `security add-generic-password -U -s
   com.unjuno.gpu-control.runner -a runner-bearer -w` and repeat with
   `-a sites-service`; `security` prompts for each value, so do not put a token
   on the command line or in a file. Deploy the exact saved Site version after
   changing its runtime secret; admission stays closed during the rotation.
2. Run `python3 runner/macos_launch_agent.py --install` from the
   `sites/gpu-control-sites` checkout. Check the installed plist has mode
   `0600` and contains no credential values.
3. Stop the existing Runner through its current process supervisor and verify
   it exited and removed any workload container. The LaunchAgent `--start`
   command refuses to start while it detects an unmanaged Runner process.
4. Run `python3 runner/macos_launch_agent.py --start`, then `--status`. Verify
   the Site reports the exact source and image ready before reopening admission.
   If already loaded, `--start` reports that state and does not force a restart.
5. For maintenance, close admission and wait for terminal runs before running
   `python3 runner/macos_launch_agent.py --stop`, then verify the process and
   workload container are gone. Preserve Keychain entries during uninstall;
   revoke credentials separately after a replacement is proven and no Runner
   depends on them.

The source SHA recorded in saved Site Version 13 was reconciled with the
Cloudflare artifact repository at that time. Version 15 is now the live Site
version. For further edits, reconcile the checkout against the deployed source
before pushing. Preserve the active Runner and its Keychain credentials while
testing changes; schedule restarts only after a live recovery plan is ready.

## Open operational acceptance

1. Rehearse credential rotation and restart with admission closed. The current
   service already has a protected Keychain secret source; prove that a planned
   replacement starts with the rotated credentials, returns exact source/image
   readiness, and leaves no orphan workload before considering this gate done.
2. Exercise cancellation, Runner interruption/restart, lease expiry, result
   reconciliation, and cleanup against the live Site and Runner.
3. Define R2 artifact retention and orphan cleanup; exercise larger artifacts and
   repeated retrieval beyond the two accepted result objects.
4. Test owner isolation across separate accounts and verify Site access revocation.
5. Add and rehearse a supported Runner start/stop, secret rotation, backup,
   restore, and incident procedure before increasing admission or enabling paid
   providers.

Detailed current state and evidence: `decisions/2026-11-11-sites-d1-architecture-pivot.md`.
