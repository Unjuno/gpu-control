const CHALLENGE_TTL_SECONDS = 600;

function randomHex(bytes = 16) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
}

async function challengeHash(token) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function issueTrainingChallenge(db, owner, runId, fingerprint, controlPlaneSha, now) {
  const token = [...crypto.getRandomValues(new Uint8Array(32))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
  const row = await db.prepare(`INSERT INTO training_authorizations
      (plan_id, owner_id, fingerprint, control_plane_sha, challenge_hash, expires_at)
    SELECT id, owner_id, fingerprint, ?, ?, MIN(expires_at, ?)
    FROM training_plans WHERE owner_id=? AND id=? AND fingerprint=? AND expires_at>?
      AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL
    ON CONFLICT(plan_id) DO UPDATE SET control_plane_sha=excluded.control_plane_sha,
      challenge_hash=excluded.challenge_hash, expires_at=excluded.expires_at, authorized_at=NULL
    WHERE training_authorizations.authorized_at IS NULL
      OR training_authorizations.expires_at<=?
      OR training_authorizations.control_plane_sha<>excluded.control_plane_sha
    RETURNING expires_at`)
    .bind(controlPlaneSha, await challengeHash(token), now + CHALLENGE_TTL_SECONDS,
      owner, runId, fingerprint, now, now).first();
  return row ? { token, expiresAt: row.expires_at } : null;
}

export async function confirmTrainingChallenge(db, owner, runId, fingerprint, controlPlaneSha, token, now) {
  const row = await db.prepare(`UPDATE training_authorizations SET authorized_at=?
    WHERE plan_id=? AND owner_id=? AND fingerprint=? AND control_plane_sha=?
      AND challenge_hash=? AND authorized_at IS NULL AND expires_at>?
      AND EXISTS (SELECT 1 FROM training_plans p
        WHERE p.id=training_authorizations.plan_id AND p.owner_id=training_authorizations.owner_id
          AND p.fingerprint=training_authorizations.fingerprint AND p.expires_at>?
          AND p.cancelled_at IS NULL AND p.dispatch_claimed_at IS NULL)
    RETURNING plan_id`)
    .bind(now, runId, owner, fingerprint, controlPlaneSha, await challengeHash(token), now, now).first();
  return Boolean(row);
}

// A ChatGPT training_submit call is the single owner confirmation boundary.
// The tool is advertised as destructive, so ChatGPT's native write confirmation
// happens before this authenticated call reaches the Worker. Persist that
// confirmation as exact, one-use evidence; do not require a separate Modal or
// browser login for every run.
export async function authorizeTrainingPlanFromMcp(db, owner, runId, fingerprint,
  controlPlaneSha, now) {
  if (typeof controlPlaneSha !== "string" || !/^[0-9a-f]{40}$/.test(controlPlaneSha)) return null;
  const id = randomHex();
  const reference = randomHex(32);
  const challenge = randomHex(32);
  const row = await db.prepare(`INSERT INTO training_authorizations
      (plan_id, owner_id, fingerprint, control_plane_sha, challenge_hash, expires_at,
       authorized_at, authorization_id, authorization_source, authorization_reference,
       decision_record_id, authorized_by, target_repository, target_sha, image_digest,
       provider, provider_resource_id, gpu_count, runtime_seconds, max_cost_microusd)
    SELECT p.id, p.owner_id, p.fingerprint, ?, ?, MIN(p.expires_at, ?), ?, ?,
       'chatgpt_mcp_write_confirmation', ?, ?, ?,
       json_extract(p.plan_json, '$.repository'), json_extract(p.plan_json, '$.commit'),
       json_extract(p.plan_json, '$.image_digest'), json_extract(p.plan_json, '$.provider'),
       json_extract(p.plan_json, '$.provider_resource_id'), json_extract(p.plan_json, '$.gpu_count'),
       json_extract(p.plan_json, '$.runtime_seconds'), json_extract(p.plan_json, '$.max_cost_microusd')
    FROM training_plans p WHERE p.owner_id=? AND p.id=? AND p.fingerprint=?
      AND p.expires_at>? AND p.cancelled_at IS NULL AND p.dispatch_claimed_at IS NULL
    ON CONFLICT(plan_id) DO UPDATE SET
      owner_id=excluded.owner_id, fingerprint=excluded.fingerprint,
      control_plane_sha=excluded.control_plane_sha, challenge_hash=excluded.challenge_hash,
      expires_at=excluded.expires_at, authorized_at=excluded.authorized_at,
      authorization_id=excluded.authorization_id, authorization_source=excluded.authorization_source,
      authorization_reference=excluded.authorization_reference, decision_record_id=excluded.decision_record_id,
      authorized_by=excluded.authorized_by, target_repository=excluded.target_repository,
      target_sha=excluded.target_sha, image_digest=excluded.image_digest, provider=excluded.provider,
      provider_resource_id=excluded.provider_resource_id, gpu_count=excluded.gpu_count,
      runtime_seconds=excluded.runtime_seconds, max_cost_microusd=excluded.max_cost_microusd,
      consumed_at=NULL
    WHERE training_authorizations.consumed_at IS NOT NULL
      OR training_authorizations.authorized_at IS NULL
      OR training_authorizations.expires_at<=?
      OR training_authorizations.control_plane_sha<>excluded.control_plane_sha
    RETURNING authorization_id, authorization_source, authorization_reference,
      decision_record_id, authorized_by, control_plane_sha, target_repository,
      target_sha, image_digest, provider, provider_resource_id, gpu_count,
      runtime_seconds, max_cost_microusd, authorized_at, expires_at`)
    .bind(controlPlaneSha, await challengeHash(challenge), now + CHALLENGE_TTL_SECONDS,
      now, id, reference, `training-plan:${runId}:${fingerprint}`, owner,
      owner, runId, fingerprint, now, now).first();
  if (row) return row;
  const existing = await db.prepare(`SELECT authorization_id, authorization_source,
      authorization_reference, decision_record_id, authorized_by, control_plane_sha,
      target_repository, target_sha, image_digest, provider, provider_resource_id,
      gpu_count, runtime_seconds, max_cost_microusd, authorized_at, expires_at
    FROM training_authorizations WHERE plan_id=? AND owner_id=? AND fingerprint=?
      AND control_plane_sha=? AND authorization_source='chatgpt_mcp_write_confirmation'
      AND authorized_by=? AND authorized_at IS NOT NULL AND expires_at>? AND consumed_at IS NULL`)
    .bind(runId, owner, fingerprint, controlPlaneSha, owner, now).first();
  return existing || null;
}
