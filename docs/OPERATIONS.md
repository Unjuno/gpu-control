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
- Repeating the same submission returns the existing run instead of starting
  another container.
- CPU admission is limited to one in-flight run and 30 seconds. The workload
  reports `gpu_used=false`; paid provider execution remains parked.

These checks prove seven provenance-valid bounded CPU inferences and three
bounded R2 artifact retrievals. They do not prove general model quality, GPU
execution, live forced-restart/cancellation recovery, cross-owner isolation,
long-term artifact retention, or backup/restore. Do not use this candidate to
claim those capabilities.

The currently deployed Site is Version 11 from source commit
`1b6916cb53e001af352808f6fd80db4dcff43999`. Cancellation support is saved as
Site Version 13 from source commit `52416ec02fcf3b755e1763edc617cd0a67f4ab91`,
but is not deployed. It adds a D1 protocol-version check so legacy Runners fail
closed. The local suite passes 24 Worker tests and 12 Runner tests; build and
artifact validation also pass. This local evidence does not establish live
cancellation behavior.

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

The tested local candidate reads both Runner credentials from the user's
login Keychain at launch and keeps them in process memory. Its LaunchAgent plist
contains only the fixed Site URL, registered source/image identity, and polling
settings. The plist is written atomically with mode `0600`; a missing Keychain
entry fails closed. The candidate has not yet replaced the currently running
ephemeral Runner.

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

The source SHA recorded in the saved Site Version 13 is not present in the
current Sites checkout. Do not deploy that version or replace the current
Runner until its source provenance has been reconciled.

## Open operational acceptance

1. Establish a persistent, protected Runner secret source and supported
   start/stop procedure, then rehearse credential rotation and restart with
   admission closed. The current process was started through an ephemeral
   launcher; its credentials are not available to a new process. Do not restart
   it until a replacement secret source is configured and the active process
   state has been checked. Verify that readiness returns only after the exact
   image and source have been checked.
2. Exercise cancellation, Runner interruption/restart, lease expiry, result
   reconciliation, and cleanup against the live Site and Runner.
3. Define R2 artifact retention and orphan cleanup; exercise larger artifacts and
   repeated retrieval beyond the two accepted result objects.
4. Test owner isolation across separate accounts and verify Site access revocation.
5. Add and rehearse a supported Runner start/stop, secret rotation, backup,
   restore, and incident procedure before increasing admission or enabling paid
   providers.

Detailed current state and evidence: `decisions/2026-11-11-sites-d1-architecture-pivot.md`.
