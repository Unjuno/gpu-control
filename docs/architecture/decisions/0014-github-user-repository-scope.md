# ADR 0014: Intersect GitHub App access with the connected user's repository scope

- **Status:** accepted for the PR #70 source candidate; migration and release are not deployed.
- **Date:** 2026-11-29
- **Scope:** GitHub repository discovery and read-token issuance for owner-selected sources.

## Context

An installation token can see every repository selected for the GitHub App
installation. That set can be broader than the repositories the person who
connected the installation may read. Checking only the App installation list
could therefore allow a Sites owner to request source from a private
organization repository that the authenticated GitHub user cannot access.

## Decision

At the one-time owner-bound OAuth callback, enumerate the authenticated user's
repositories for the exact installation using GitHub's user-token endpoint.
Persist only the validated lower-case repository names; do not persist the
short-lived GitHub user token. Repository discovery and exact repository
read-token issuance intersect this saved user-authorized set with the current
App installation repository list. The App token remains read-only and is
minted for one exact repository. Migration 0041 clears connections created by
the earlier source candidate because they have no recorded user repository
scope; the owner must reconnect before source reads.

## Consequences

- A repository absent from the user's OAuth-authorized installation list
  cannot be discovered or receive an installation read token through the
  Sites source flow.
- A repository added after connection requires reconnecting to refresh the
  saved scope.
- Removal of a user's GitHub access is not observed continuously by this
  snapshot. Disconnect the GitHub App connection or reconnect after an access
  change. A future design needing immediate revocation must retain an encrypted
  renewable user authorization or revalidate the user on every source access.
- The scope is capped at 500 repositories and 128 KiB; malformed, incomplete,
  duplicate, or oversized responses fail closed.
- This is a source-level security boundary. It does not enable arbitrary
  commands, expose provider credentials, enable admission, or publish a live
  execution route.

## Revisit when

- GitHub changes the user-token installation repository endpoint or access
  semantics;
- immediate permission revocation becomes a release requirement; or
- the Site gains a verified, current GitHub identity that can replace this
  owner-bound setup flow.
