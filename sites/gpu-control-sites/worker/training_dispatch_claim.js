import { prepareModalComputeBudgetReservation, utcMonthKey } from "./provider_budget_policy.js";
import { MAP_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";

// Authorization must already be established. This single write reserves the
// whole plan ceiling and prevents concurrent or duplicate dispatch claims.
export async function claimTrainingDispatch(db, owner, runId, fingerprint, now, monthlyLimit, authorization,
  maxMonthlyLimit = MAP_TRAINING_MAX_MONTHLY_MICROUSD, modalReservation = null) {
  if (!Number.isSafeInteger(monthlyLimit) || monthlyLimit < 1 ||
      !Number.isSafeInteger(maxMonthlyLimit) || maxMonthlyLimit < 1 || monthlyLimit > maxMonthlyLimit) {
    throw new Error("TRAINING_BUDGET_NOT_CONFIGURED");
  }
  if (!authorization || !["site_owner_plan_confirmation", "chatgpt_mcp_write_confirmation"]
      .includes(authorization.authorization_source) ||
      authorization.authorized_by !== owner || authorization.decision_record_id !== `training-plan:${runId}:${fingerprint}` ||
      !/^[0-9a-f]{40}$/.test(authorization.control_plane_sha || "") ||
      !/^[0-9a-f]{32}$/.test(authorization.authorization_id || "") ||
      !/^[0-9a-f]{64}$/.test(authorization.authorization_reference || "")) {
    throw new Error("TRAINING_AUTHORIZATION_INVALID");
  }
  const date = new Date(now * 1000);
  const monthStart = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1) / 1000;
  const periodKey = utcMonthKey(now);
  const budgetReservation = modalReservation ? {
    runId, source: modalReservation.source, fingerprint, periodKey,
    requestedMicrousd: modalReservation.requestedMicrousd, now, requireGpuAdmission: true,
  } : null;
  const budgetInsert = budgetReservation ? prepareModalComputeBudgetReservation(db, budgetReservation) : null;
  const modalBudgetClaimGate = budgetReservation ? `
      AND EXISTS (SELECT 1 FROM modal_gpu_admission_policy b
        WHERE b.scope='workspace' AND b.admission_enabled=1)
      AND EXISTS (SELECT 1 FROM modal_compute_budget_reservations r
        WHERE r.run_id=? AND r.source=? AND r.plan_fingerprint=? AND r.period_key=? AND r.reserved_microusd=?)` : "";
  const claimStatement = db.prepare(`UPDATE training_plans SET dispatch_claimed_at=?
    WHERE owner_id=? AND id=? AND fingerprint=?
      AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL AND expires_at>?
      AND NOT EXISTS (SELECT 1 FROM training_plans p WHERE p.owner_id=training_plans.owner_id
        AND p.id<>training_plans.id AND p.dispatch_claimed_at IS NOT NULL
        AND p.dispatch_rejection IS NULL AND p.cleanup_confirmed_at IS NULL)
      AND EXISTS (SELECT 1 FROM training_authorizations a WHERE a.plan_id=training_plans.id
        AND a.owner_id=training_plans.owner_id AND a.fingerprint=training_plans.fingerprint
        AND a.authorization_id=? AND a.authorization_reference=? AND a.control_plane_sha=?
        AND a.authorization_source IN ('site_owner_plan_confirmation','chatgpt_mcp_write_confirmation') AND a.authorized_by=?
        AND a.decision_record_id=? AND a.authorized_at IS NOT NULL
        AND a.consumed_at IS NULL AND a.expires_at>?)
      ${modalBudgetClaimGate}
      AND json_extract(plan_json, '$.max_cost_microusd') +
        COALESCE((SELECT SUM(json_extract(p.plan_json, '$.max_cost_microusd'))
          FROM training_plans p WHERE p.dispatch_claimed_at>=?), 0) <= ?
    RETURNING plan_json`).bind(now, owner, runId, fingerprint, now, authorization.authorization_id,
      authorization.authorization_reference, authorization.control_plane_sha, owner,
      authorization.decision_record_id, now,
      ...(budgetReservation ? [runId, budgetReservation.source, fingerprint, periodKey,
        budgetReservation.requestedMicrousd] : []), monthStart, monthlyLimit);
  const authorizationStatement = db.prepare(`UPDATE training_authorizations SET consumed_at=?
      WHERE plan_id=? AND owner_id=? AND fingerprint=? AND control_plane_sha=?
        AND authorization_id=? AND authorization_reference=?
        AND authorization_source IN ('site_owner_plan_confirmation','chatgpt_mcp_write_confirmation') AND authorized_by=?
        AND decision_record_id=? AND authorized_at IS NOT NULL AND expires_at>?
        AND consumed_at IS NULL AND EXISTS (SELECT 1 FROM training_plans p
          WHERE p.id=training_authorizations.plan_id AND p.owner_id=training_authorizations.owner_id
            AND p.fingerprint=training_authorizations.fingerprint AND p.dispatch_claimed_at=?)`)
      .bind(now, runId, owner, fingerprint, authorization.control_plane_sha,
        authorization.authorization_id, authorization.authorization_reference, owner,
        authorization.decision_record_id, now, now);
  const cleanupReservation = budgetReservation ? db.prepare(`DELETE FROM modal_compute_budget_reservations
    WHERE run_id=? AND source=? AND plan_fingerprint=? AND period_key=? AND reserved_microusd=?
      AND NOT EXISTS (SELECT 1 FROM training_plans p WHERE p.id=? AND p.owner_id=?
        AND p.fingerprint=? AND p.dispatch_claimed_at=?)`)
    .bind(runId, budgetReservation.source, fingerprint, periodKey,
      budgetReservation.requestedMicrousd, runId, owner, fingerprint, now) : null;
  const statements = budgetInsert
    ? [budgetInsert, claimStatement, authorizationStatement, cleanupReservation]
    : [claimStatement, authorizationStatement];
  const claimIndex = budgetInsert ? 1 : 0;
  const results = await db.batch(statements);
  return results?.[claimIndex]?.results?.[0] || null;
}

