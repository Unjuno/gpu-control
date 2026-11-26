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
  const token = randomHex(32);
  const row = await db.prepare(`INSERT INTO training_authorizations
      (plan_id, owner_id, fingerprint, control_plane_sha, challenge_hash, expires_at)
    SELECT id, owner_id, fingerprint, ?, ?, MIN(expires_at, ?)
    FROM training_plans WHERE owner_id=? AND id=? AND fingerprint=? AND expires_at>?
      AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL
    ON CONFLICT(plan_id) DO UPDATE SET control_plane_sha=excluded.control_plane_sha,
      challenge_hash=excluded.challenge_hash, expires_at=excluded.expires_at, authorized_at=NULL,
      authorization_id=NULL, authorization_source=NULL, authorization_reference=NULL,
      decision_record_id=NULL, authorized_by=NULL, target_repository=NULL, target_sha=NULL,
      image_digest=NULL, provider=NULL, provider_resource_id=NULL, gpu_count=NULL,
      runtime_seconds=NULL, max_cost_microusd=NULL, consumed_at=NULL
    WHERE training_authorizations.authorized_at IS NULL
      OR training_authorizations.expires_at<=?
      OR training_authorizations.control_plane_sha<>excluded.control_plane_sha
    RETURNING expires_at`)
    .bind(controlPlaneSha, await challengeHash(token), now + CHALLENGE_TTL_SECONDS,
      owner, runId, fingerprint, now, now).first();
  return row ? { token, expiresAt: row.expires_at } : null;
}

export async function confirmTrainingChallenge(db, owner, runId, fingerprint, controlPlaneSha, token, now) {
  const plan = await db.prepare(`SELECT p.plan_json FROM training_plans p
    WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.expires_at>?
      AND p.cancelled_at IS NULL AND p.dispatch_claimed_at IS NULL`)
    .bind(runId, owner, fingerprint, now).first();
  if (!plan || typeof controlPlaneSha !== "string" || !/^[0-9a-f]{40}$/.test(controlPlaneSha)) return false;
  let execution;
  try { execution = JSON.parse(plan.plan_json); } catch { return false; }
  const authorizationId = randomHex(16);
  const authorizationReference = randomHex(32);
  const row = await db.prepare(`UPDATE training_authorizations SET authorized_at=?,
      authorization_id=?, authorization_source='site_owner_plan_confirmation',
      authorization_reference=?, decision_record_id=?, authorized_by=?,
      target_repository=?, target_sha=?, image_digest=?, provider=?,
      provider_resource_id=?, gpu_count=?, runtime_seconds=?, max_cost_microusd=?
    WHERE plan_id=? AND owner_id=? AND fingerprint=? AND control_plane_sha=?
      AND challenge_hash=? AND authorized_at IS NULL AND expires_at>?
      AND EXISTS (SELECT 1 FROM training_plans p
        WHERE p.id=training_authorizations.plan_id AND p.owner_id=training_authorizations.owner_id
          AND p.fingerprint=training_authorizations.fingerprint AND p.expires_at>?
          AND p.cancelled_at IS NULL AND p.dispatch_claimed_at IS NULL)
    RETURNING plan_id`)
    .bind(now, authorizationId, authorizationReference, `training-plan:${runId}:${fingerprint}`,
      owner, execution.repository, execution.commit, execution.image_digest, execution.provider,
      execution.provider_resource_id, execution.gpu_count, execution.runtime_seconds,
      execution.max_cost_microusd, runId, owner, fingerprint, controlPlaneSha,
      await challengeHash(token), now, now).first();
  return Boolean(row);
}

export async function getTrainingAuthorization(db, owner, runId, fingerprint) {
  return db.prepare(`SELECT authorization_id, authorization_source, authorization_reference,
      decision_record_id, authorized_by, control_plane_sha, target_repository,
      target_sha, image_digest, provider, provider_resource_id, gpu_count,
      runtime_seconds, max_cost_microusd, authorized_at, expires_at, consumed_at
    FROM training_authorizations WHERE plan_id=? AND owner_id=? AND fingerprint=?`)
    .bind(runId, owner, fingerprint).first();
}
