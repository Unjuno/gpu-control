# Built-in OAuth issuer migration acceptance

Status: **LOCAL FIXTURE AND FOUR POSTGRESQL PROCESS-KILL BOUNDARIES PASS; production and independent acceptance NOT RUN**.

The offline command `python -m gpu_gateway.owner_migration` was exercised with
a temporary SQLite database and artifact directory. The twelve focused tests
cover read-only preflight, migration of a settled run, `submission_intent.owner`,
artifact copy and retrieval under the destination owner, retained rollback
copy, local token/session invalidation, resumption after destination-scope
installation, rebuilding partial rollback/staging directories, and fail-closed
handling of unsettled runs, idempotency collisions, and artifact corruption.
An additional race regression changes the source result after preflight artifact
verification; migration now rejects the complete changed run-row snapshot before
installing a destination scope, preserving the old owner and artifact authority.
They also verify the migrated owner can list/status/result/artifact-read the
run while the old and an unrelated owner see an empty list and receive 404 for
object reads; a nonzero global active-slot counter is also refused. A separate
local disposable PostgreSQL 16
container (digest
`sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97`)
also passed preflight, DB update, artifact readback, and token revocation using
synthetic rows. A separate disposable PostgreSQL 16 run held the control row,
waited until destination artifacts were installed and the migration process
was blocked before its DB update, then sent SIGKILL. The DB still named the old
owner, the old artifact remained readable, and retrying the migration
successfully completed the owner change and new-scope readback. Two more
PostgreSQL 16 child processes used a controlled `copytree` wrapper that wrote a
partial rollback or staging directory and blocked before returning; each
process was SIGKILLed at that point. In both cases, the DB and old artifacts
remained usable and retry rebuilt the partial directory and completed the
migration. A separate PostgreSQL 16 process was SIGKILLed after DB commit; the
new owner could list the run, read its result and artifact, and its OAuth token
was revoked. All four containers and their artifact fixtures were removed. The
combined owner-migration, experiment API, artifact, and local-OAuth suites
passed 34 tests with one Starlette deprecation warning. The command help,
Python compilation, and `git diff --check` also passed.

These are synthetic local fixtures. They do not prove behavior on the selected
production PostgreSQL service, process interruption at other filesystem/DB
boundaries, production filesystem quota behavior, issuer/OAuth behavior in a
live ChatGPT connection, or independent owner-isolation review. They do not satisfy
the P3 roadmap item by itself. Before production use, run the procedure against
a disposable PostgreSQL restore plus real artifact-volume copy; verify all
owner-scoped list/status/result/artifact paths with the migrated identity and
an unrelated identity; test refusal/rollback/retry boundaries; and retain the
operation log without tokens, owner credentials, or row contents.
