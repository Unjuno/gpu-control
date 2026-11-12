# P5 paid authorization persistence foundation — 2026-10-31

Status: **PARTIAL / NOT ACCEPTANCE**

Schema v12 adds a dedicated `gateway_paid_authorizations_v1` table. The Store
write primitive accepts only a verifier result plus its signed envelope, then
rechecks that the run is still approved under the exact `approval_id`, owner,
and plan fingerprint before persisting. A changed browser approval invalidates
the previous record. Reload requires the same binding tuple and verifies the
canonical envelope digest and size bound.

This is not an issuer, public API, worker integration, revocation service, or
provider authorization. There is no caller yet, and the Worker retains its
`runpod_authorization_persistence_unavailable` refusal. No signed authorization
was issued, persisted, or used. Paid execution and all RunPod live calls remain
disabled; repository policy remains `mode: parked`.

Validation in this change: Gateway dedicated-venv tests passed **4/4** for
exact binding, expiry, approval replacement, reload identity, and tamper
detection; migration tests passed **10/10**. Python syntax compilation and
`git diff --check` passed. These Store tests use SQLite. PostgreSQL execution,
independent security review, and a real verifier-to-Store caller remain
required before changing the worker gate. No live provider calls were run.

## Read-time approval revalidation follow-up

The Store read now locks and checks the current run row, exact approval ID,
owner and plan fingerprint, live browser approval expiry, envelope identity,
envelope expiry, and canonical digest. It permits `approved` and `submitting`:
`Worker.claim` transitions a queued run to `submitting` before pre-intent
validation. It rejects recovery and terminal states and requires
`cancel_requested` to be literal false, so a cancellation committed before the
read cannot pass this gate. The row lock ends when the read transaction
returns; a cancellation that commits afterward can still race a later provider
call. Worker integration must recheck cancellation at its submission boundary
and handle a cancel that arrives after provider acceptance. The issuer
signature and current revocation status still require caller-side verification;
the reader is not yet wired to Worker. Focused Store tests pass **5/5**,
including submitting state, a previously committed cancellation, browser
approval expiry, envelope expiry, and terminal state refusal. This follow-up
does not open the RunPod authorization gate.
