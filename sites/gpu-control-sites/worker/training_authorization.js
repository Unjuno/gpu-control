const CHALLENGE_TTL_SECONDS = 600;

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
