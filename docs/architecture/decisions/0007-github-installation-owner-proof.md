# ADR 0007: Prove GitHub installation access before binding it to a Sites owner

- **Status:** accepted for the PR #70 source candidate; deployment is not approved.
- **Date:** 2026-11-28
- **Scope:** one-time GitHub App connection used to read an owner-selected
  training repository.

## Context

GitHub redirects an App installation to its configured Setup URL with an
installation_id. The ID establishes which App installation GitHub reports,
but does not prove that the person who initiated the redirect can access that
installation. The previous callback bound the ID to the authenticated Sites
owner using only the Sites state and App-authenticated installation metadata.
That leaves an account-linking gap: a spoofed callback could attempt to bind a
different valid installation.

The product needs a one-time account connection. Requiring a provider login or
owner confirmation for each experiment would obstruct ordinary ChatGPT
conversation; trusting the installation ID alone would bind the wrong
principal.

## Decision

1. github_connection_start creates a short-lived, random state bound to the
   authenticated Sites owner.
2. The App Setup callback validates the callback state, fetches the exact
   installation as the GitHub App, and checks selected-repository,
   unsuspended, read-only permissions.
3. Before binding, the browser completes GitHub App user authorization using a
   second random state and PKCE S256 challenge. The state hash and pending
   installation identity are stored with a short expiry. The PKCE verifier is
   held in a short-lived Secure, HttpOnly, SameSite=Lax, host-only cookie.
4. The callback exchanges the one-time code server-side, then uses the returned
   user token to request repository access for the exact installation ID.
   Failure, expiry, state mismatch, or replay prevents binding.
5. The owner binding is saved atomically with one-time state consumption.
   Neither the GitHub user token nor the installation token is persisted. The
   later installation token is minted for the selected repository name, and
   its returned full repository name and read permissions are verified.
6. Forward migration 0033 clears older installation bindings and pending
   setup states because their owner identity was not verified. Each connected
   owner must repeat the one-time connection after the migration.

The user token proves that the GitHub-authorized user can access the target
installation; it does not identify the Sites owner by matching email or
username. The owner relationship comes from the short-lived, owner-bound
Sites state. No GitHub username or email becomes a Sites authorization key.

## Consequences

- The Site requires the GitHub App OAuth client ID, client secret, and exact
  OAuth callback URL in server-side secret storage, in addition to App ID,
  slug, and private key.
- The GitHub App Setup URL and OAuth Callback URL are separate settings:
  /github/setup and /github/oauth/callback.
- Setup is still a one-time account connection. Experiment plans and submits
  do not request these OAuth credentials or repeat the GitHub login.
- Existing installations are deliberately disconnected by migration 0033;
  registrations and experiment history are unaffected.
- Tests prove callback state, PKCE generation and exchange, access denial,
  token non-persistence, migration behavior, and repository-scoped token
  requests. They do not replace independent security review or hosted flow
  verification.

## Revisit when

- ChatGPT Sites authentication offers a verified GitHub identity that can be
  securely bound to the installation;
- GitHub changes Setup URL or user-token behavior; or
- the application needs organization-specific user authorization controls.
