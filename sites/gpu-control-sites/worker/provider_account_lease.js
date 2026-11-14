const SHA256_RE = /^[0-9a-f]{64}$/;
const PROVIDER_JOB_ID_RE = /^[A-Za-z0-9_-]{1,128}$/;
const LEASE_STATES = new Set(["reserved", "submitting", "uncertain", "active", "cleanup_pending", "released"]);
const TRANSITIONS = {
  reserved: new Set(["submitting", "released"]),
  submitting: new Set(["active", "uncertain", "released"]),
  uncertain: new Set(["active", "cleanup_pending"]),
  active: new Set(["cleanup_pending"]),
  cleanup_pending: new Set(["released"]),
  released: new Set(),
};

export class ProviderAccountLeaseError extends Error {
  constructor(code) {
    super(code);
    this.name = "ProviderAccountLeaseError";
    this.code = code;
  }
}

function requireText(value, name, maximum = 256) {
  if (typeof value !== "string" || value.length < 1 || value.length > maximum || value !== value.trim()) {
    throw new ProviderAccountLeaseError(`INVALID_${name.toUpperCase()}`);
  }
}

function requireDigest(value, name) {
  if (typeof value !== "string" || !SHA256_RE.test(value)) {
    throw new ProviderAccountLeaseError(`INVALID_${name.toUpperCase()}`);
  }
}

function requireTimestamp(value) {
  if (!Number.isSafeInteger(value) || value < 0) throw new ProviderAccountLeaseError("INVALID_TIMESTAMP");
}

function randomHex(bytes = 32) {
  const raw = new Uint8Array(bytes);
  crypto.getRandomValues(raw);
  return Array.from(raw, (value) => value.toString(16).padStart(2, "0")).join("");
}

function fromBase64(value) {
  if (typeof value !== "string" || !value || value.length > 8192 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
    throw new ProviderAccountLeaseError("INVALID_ACCOUNT_SCOPE_HMAC_KEY");
  }
  const binary = atob(value);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  if (bytes.length < 32 || bytes.length > 4096) throw new ProviderAccountLeaseError("INVALID_ACCOUNT_SCOPE_HMAC_KEY");
  return bytes;
}

export async function deriveProviderAccountScopeHash({ scopeId, hmacKeyB64 }) {
  requireText(scopeId, "account_scope_id", 128);
  const keyBytes = fromBase64(hmacKeyB64);
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const message = new TextEncoder().encode(`gpu-control/provider-account-scope/v1/runpod\0${scopeId}`);
  const digest = new Uint8Array(await crypto.subtle.sign("HMAC", key, message));
  keyBytes.fill(0);
  return Array.from(digest, (value) => value.toString(16).padStart(2, "0")).join("");
}

function leaseInput(input) {
  requireDigest(input.accountScopeSha256, "account_scope_sha256");
  requireText(input.runId, "run_id", 64);
  requireText(input.ownerId, "owner_id", 256);
  requireText(input.planId, "plan_id", 64);
  requireDigest(input.planFingerprint, "plan_fingerprint");
  requireText(input.authorizationId, "authorization_id", 64);
  requireDigest(input.challengeSha256, "challenge_sha256");
  requireTimestamp(input.now);
}

function rowFromBatch(result) {
  return result?.results?.[0] ?? null;
}

export async function reserveProviderAccountLease(db, input) {
  leaseInput(input);
  const leaseToken = randomHex();
  const eventId = randomHex();
  const now = input.now;
  await db.batch([
    db.prepare(`INSERT INTO provider_account_leases (
        provider, account_scope_sha256, generation, revision, lease_token,
        run_id, owner_id, plan_fingerprint, authorization_id, challenge_sha256,
        state, provider_job_id, release_evidence_type, release_evidence_sha256,
        created_at, updated_at, released_at
      )
      SELECT 'runpod', ?, 1, 1, ?, r.id, r.owner_id, p.fingerprint, a.id, ?,
        'reserved', NULL, NULL, NULL, ?, ?, NULL
      FROM runs r JOIN plans p ON p.id = r.plan_id
      JOIN human_authorizations a ON a.plan_id = p.id
      WHERE r.id = ? AND r.owner_id = ? AND r.plan_id = ? AND r.state = 'queued'
        AND r.cleanup_state = 'pending' AND p.owner_id = r.owner_id
        AND p.fingerprint = ? AND a.id = ? AND a.owner_id = r.owner_id
        AND a.fingerprint = p.fingerprint AND a.consumed_at IS NOT NULL
      ON CONFLICT(provider, account_scope_sha256) DO UPDATE SET
        generation = provider_account_leases.generation + 1,
        revision = 1,
        lease_token = excluded.lease_token,
        run_id = excluded.run_id,
        owner_id = excluded.owner_id,
        plan_fingerprint = excluded.plan_fingerprint,
        authorization_id = excluded.authorization_id,
        challenge_sha256 = excluded.challenge_sha256,
        state = 'reserved',
        provider_job_id = NULL,
        release_evidence_type = NULL,
        release_evidence_sha256 = NULL,
        created_at = excluded.created_at,
        updated_at = excluded.updated_at,
        released_at = NULL
      WHERE provider_account_leases.state = 'released'
      RETURNING provider, account_scope_sha256, generation, revision, lease_token,
        run_id, owner_id, plan_fingerprint, authorization_id, challenge_sha256,
        state, provider_job_id, created_at, updated_at`)
      .bind(input.accountScopeSha256, leaseToken, input.challengeSha256, now, now,
        input.runId, input.ownerId, input.planId, input.planFingerprint, input.authorizationId),
    db.prepare(`INSERT INTO provider_account_lease_events (
        event_id, provider, account_scope_sha256, generation, revision, run_id,
        from_state, to_state, evidence_type, evidence_sha256, created_at
      )
      SELECT ?, provider, account_scope_sha256, generation, revision, run_id,
        NULL, 'reserved', 'plan_and_authorization_bound', challenge_sha256, ?
      FROM provider_account_leases
      WHERE provider = 'runpod' AND account_scope_sha256 = ? AND lease_token = ? AND state = 'reserved'
      ON CONFLICT(provider, account_scope_sha256, generation, revision) DO NOTHING`)
      .bind(eventId, now, input.accountScopeSha256, leaseToken),
  ]);

  const current = await db.prepare(`SELECT provider, account_scope_sha256, generation, revision, lease_token,
      run_id, owner_id, plan_fingerprint, authorization_id, challenge_sha256, state, provider_job_id,
      release_evidence_type, release_evidence_sha256, created_at, updated_at, released_at
    FROM provider_account_leases WHERE provider='runpod' AND account_scope_sha256=?`)
    .bind(input.accountScopeSha256).first();
  if (!current) throw new ProviderAccountLeaseError("RUN_AUTHORIZATION_OR_SUBMISSION_INTENT_INVALID");
  const sameIntent = current.run_id === input.runId && current.owner_id === input.ownerId &&
    current.plan_fingerprint === input.planFingerprint && current.authorization_id === input.authorizationId &&
    current.challenge_sha256 === input.challengeSha256;
  if (current.lease_token === leaseToken && sameIntent && current.state === "reserved") return current;
  if (sameIntent && current.state !== "released") return current;
  throw new ProviderAccountLeaseError("PROVIDER_ACCOUNT_LEASE_BUSY");
}

function validateTransition(from, to, input) {
  if (!LEASE_STATES.has(from) || !LEASE_STATES.has(to) || !TRANSITIONS[from]?.has(to)) {
    throw new ProviderAccountLeaseError("PROVIDER_ACCOUNT_LEASE_TRANSITION_DENIED");
  }
  if (to === "active" || to === "cleanup_pending") {
    if (!PROVIDER_JOB_ID_RE.test(input.providerJobId ?? "")) throw new ProviderAccountLeaseError("INVALID_PROVIDER_JOB_ID");
  } else if (to !== "released" && input.providerJobId != null) {
    throw new ProviderAccountLeaseError("UNEXPECTED_PROVIDER_JOB_ID");
  }
  if (to === "released") {
    const expectedEvidence = from === "reserved" || from === "submitting" ? "provider_create_not_started" :
      from === "cleanup_pending" ? "pod_termination_confirmed" : null;
    if (!expectedEvidence || input.evidenceType !== expectedEvidence) {
      throw new ProviderAccountLeaseError("PROVIDER_ACCOUNT_LEASE_RELEASE_EVIDENCE_REQUIRED");
    }
    requireDigest(input.evidenceSha256, "release_evidence_sha256");
  } else {
    requireText(input.evidenceType, "evidence_type", 64);
    requireDigest(input.evidenceSha256, "evidence_sha256");
  }
}

export async function transitionProviderAccountLease(db, input) {
  requireDigest(input.accountScopeSha256, "account_scope_sha256");
  requireDigest(input.leaseToken, "lease_token");
  if (!Number.isSafeInteger(input.generation) || input.generation < 1 ||
      !Number.isSafeInteger(input.revision) || input.revision < 1) {
    throw new ProviderAccountLeaseError("INVALID_LEASE_VERSION");
  }
  requireTimestamp(input.now);
  const current = await db.prepare(`SELECT provider, account_scope_sha256, generation, revision, lease_token,
      run_id, owner_id, plan_fingerprint, authorization_id, challenge_sha256, state, provider_job_id
    FROM provider_account_leases WHERE provider='runpod' AND account_scope_sha256=?`)
    .bind(input.accountScopeSha256).first();
  if (!current || current.lease_token !== input.leaseToken || current.generation !== input.generation || current.revision !== input.revision) {
    throw new ProviderAccountLeaseError("STALE_PROVIDER_ACCOUNT_LEASE");
  }
  validateTransition(current.state, input.toState, input);
  const nextRevision = current.revision + 1;
  const eventId = randomHex();
  const jobId = input.toState === "active" || input.toState === "cleanup_pending"
    ? input.providerJobId : current.provider_job_id;
  const released = input.toState === "released";
  const evidenceType = released ? input.evidenceType : null;
  const evidenceSha256 = released ? input.evidenceSha256 : null;
  const results = await db.batch([
    db.prepare(`UPDATE provider_account_leases SET state=?, provider_job_id=?, revision=?, updated_at=?,
        release_evidence_type=?, release_evidence_sha256=?, released_at=?
      WHERE provider='runpod' AND account_scope_sha256=? AND lease_token=? AND generation=?
        AND revision=? AND state=?
        AND (? <> 'released' OR (
          (? IN ('reserved', 'submitting') AND ? = 'provider_create_not_started') OR
          (? = 'cleanup_pending' AND ? = 'pod_termination_confirmed' AND EXISTS (
            SELECT 1 FROM runs r WHERE r.id=provider_account_leases.run_id
              AND r.owner_id=provider_account_leases.owner_id
              AND r.state IN ('succeeded','failed','cancelled')
              AND r.cleanup_state='confirmed' AND r.cleanup_receipt_json IS NOT NULL
          ))
        ))
      RETURNING provider, account_scope_sha256, generation, revision, lease_token,
        run_id, owner_id, plan_fingerprint, authorization_id, challenge_sha256, state,
        provider_job_id, release_evidence_type, release_evidence_sha256, created_at, updated_at, released_at`)
      .bind(input.toState, jobId, nextRevision, input.now, evidenceType, evidenceSha256, released ? input.now : null,
        input.accountScopeSha256, input.leaseToken, input.generation, input.revision, current.state,
        input.toState, current.state, input.evidenceType, current.state, input.evidenceType),
    db.prepare(`INSERT INTO provider_account_lease_events (
        event_id, provider, account_scope_sha256, generation, revision, run_id,
        from_state, to_state, evidence_type, evidence_sha256, created_at
      )
      SELECT ?, provider, account_scope_sha256, generation, revision, run_id,
        ?, ?, ?, ?, ? FROM provider_account_leases
      WHERE provider='runpod' AND account_scope_sha256=? AND lease_token=? AND generation=? AND revision=? AND state=?
      ON CONFLICT(provider, account_scope_sha256, generation, revision) DO NOTHING`)
      .bind(eventId, current.state, input.toState, input.evidenceType, input.evidenceSha256, input.now,
        input.accountScopeSha256, input.leaseToken, input.generation, nextRevision, input.toState),
  ]);
  if (!rowFromBatch(results[0])) throw new ProviderAccountLeaseError("PROVIDER_ACCOUNT_LEASE_RELEASE_GATE_OR_REVISION_FAILED");
  const updated = await db.prepare(`SELECT provider, account_scope_sha256, generation, revision, lease_token,
      run_id, owner_id, plan_fingerprint, authorization_id, challenge_sha256, state, provider_job_id,
      release_evidence_type, release_evidence_sha256, created_at, updated_at, released_at
    FROM provider_account_leases WHERE provider='runpod' AND account_scope_sha256=?`)
    .bind(input.accountScopeSha256).first();
  return updated;
}
