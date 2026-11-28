import { sha256Hex } from "./sha256.js";

const CHALLENGE_TTL_SECONDS = 600;

function randomHex(bytes = 16) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
}

async function challengeHash(token) { return sha256Hex(token); }

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

// A destructive ChatGPT MCP call is the human-facing confirmation surface for
// owner-selected runs. Bind that exact call to the persisted plan; do not send
// the user to a separate browser confirmation page for each experiment.
export async function authorizeTrainingChatSubmit(db, owner, runId, fingerprint, controlPlaneSha, now) {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/.test(owner || "") ||
      !/^[0-9a-f]{32}$/.test(runId || "") || !/^[0-9a-f]{64}$/.test(fingerprint || "") ||
      !/^[0-9a-f]{40}$/.test(controlPlaneSha || "") || !Number.isSafeInteger(now)) return false;
  const challenge = randomHex(32);
  const authorizationId = randomHex(16);
  const authorizationReference = randomHex(32);
  const row = await db.prepare(`INSERT INTO training_authorizations
      (plan_id, owner_id, fingerprint, control_plane_sha, challenge_hash, expires_at,
       authorized_at, authorization_id, authorization_source, authorization_reference,
       decision_record_id, authorized_by, target_repository, target_sha, image_digest,
       provider, provider_resource_id, gpu_count, runtime_seconds, max_cost_microusd, consumed_at)
    SELECT p.id, p.owner_id, p.fingerprint, ?, ?, MIN(p.expires_at, ?), ?, ?,
       'chatgpt_mcp_write_confirmation', ?, ?, ?, json_extract(p.plan_json, '$.repository'),
       json_extract(p.plan_json, '$.commit'), json_extract(p.plan_json, '$.image_digest'),
       json_extract(p.plan_json, '$.provider'), json_extract(p.plan_json, '$.provider_resource_id'),
       json_extract(p.plan_json, '$.gpu_count'), json_extract(p.plan_json, '$.runtime_seconds'),
       json_extract(p.plan_json, '$.max_cost_microusd'), NULL
    FROM training_plans p WHERE p.owner_id=? AND p.id=? AND p.fingerprint=? AND p.expires_at>?
      AND p.cancelled_at IS NULL AND p.dispatch_claimed_at IS NULL
      AND json_extract(p.plan_json, '$.execution_kind')='owner_selected_python'
      AND json_extract(p.plan_json, '$.control_plane_sha')=?
    ON CONFLICT(plan_id) DO UPDATE SET control_plane_sha=excluded.control_plane_sha,
       challenge_hash=excluded.challenge_hash, expires_at=excluded.expires_at,
       authorized_at=excluded.authorized_at, authorization_id=excluded.authorization_id,
       authorization_source=excluded.authorization_source,
       authorization_reference=excluded.authorization_reference,
       decision_record_id=excluded.decision_record_id, authorized_by=excluded.authorized_by,
       target_repository=excluded.target_repository, target_sha=excluded.target_sha,
       image_digest=excluded.image_digest, provider=excluded.provider,
       provider_resource_id=excluded.provider_resource_id, gpu_count=excluded.gpu_count,
       runtime_seconds=excluded.runtime_seconds, max_cost_microusd=excluded.max_cost_microusd,
       consumed_at=NULL
    WHERE training_authorizations.expires_at<=? AND training_authorizations.consumed_at IS NULL
    RETURNING plan_id`)
    .bind(controlPlaneSha, challenge, now + CHALLENGE_TTL_SECONDS, now, authorizationId,
      authorizationReference, `training-plan:${runId}:${fingerprint}`, owner,
      owner, runId, fingerprint, now, controlPlaneSha, now).first();
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
