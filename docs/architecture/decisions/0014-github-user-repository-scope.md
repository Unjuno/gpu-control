# ADR 0014: Revalidate owner GitHub access for every source operation

- **Status:** accepted for the PR #70 source candidate; migration and release are not deployed.
- **Date:** 2026-11-29
- **Scope:** GitHub repository discovery and read-token issuance for owner-selected sources.

## Context

The installation token can read every repository selected for the GitHub App
installation. That set can be broader than the repositories the authenticated
GitHub user may currently access. A permanent repository-name snapshot also
keeps granting source access after the user's GitHub permission is removed.

The product is for the authenticated owner's own ChatGPT workflows. Public
source or Site visibility does not grant callers the owner's GitHub or provider
credentials. Authentication, owner isolation, and budget enforcement define
the security boundary; this design does not make provider secrets available to
other Sites users.

## Decision

At GitHub App connection time, require user authorization for the exact
installation and request an expiring user token plus its rotating refresh
token. Encrypt both at rest with AES-GCM using a dedicated 32-byte Worker
secret and additional authenticated data bound to the Sites owner, GitHub user
ID, and token type. Never return either token to ChatGPT or workload code.

Before listing repositories or minting a repository-scoped installation token,
refresh the user token when needed, verify its current GitHub identity against
the owner binding, and enumerate the user's current repositories for that exact
installation. Intersect those repository IDs with both the IDs authorized at
connection time and the current GitHub App installation list. Match by
immutable GitHub repository ID rather than name so a rename cannot substitute a
different repository. Mint the existing read-only installation token for one
exact repository only after all three checks pass.

Migration 0042 adds encrypted credential fields and expiry metadata, then
clears old connection rows so the owner must reconnect. The user access token
is short-lived and refreshed through GitHub's rotating refresh-token flow; a
revoked or expired authorization fails closed and requires reconnection.

## Consequences

- Removing the user's GitHub access blocks later source reads and read-token
  issuance even if the GitHub App installation still includes that repository.
- A repository newly added to the user's access scope requires reconnecting,
  which refreshes the original authorization snapshot.
- User and refresh tokens are encrypted at rest and never exposed to the MCP
  client. The encryption key must be stored as a Worker secret, not in D1,
  repository files, or logs.
- GitHub user-token and installation-repository pages use 25 entries to stay
  within the bounded response parser. Incomplete, duplicate, malformed,
  oversized, expired, or unauthorized data fails closed.
- This boundary does not enable arbitrary commands, expose provider
  credentials, change provider budgets, enable admission, or publish a live
  execution route.

## Revisit when

- GitHub changes its expiring user-token refresh or repository-access APIs;
- the Site adopts a verified credential broker that removes the need to store
  encrypted renewable GitHub authorization; or
- owner identity and repository selection semantics change.
