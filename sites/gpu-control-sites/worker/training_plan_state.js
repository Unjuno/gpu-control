import { getTrainingAuthorization, supportsMcpTrainingSubmit, trainingAuthorizationUrl } from "./training_authorization.js";
import { assessModalTrainingBudget, readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { ownerTrainingAdmissionEnabled } from "./training_runtime_profile.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";

export async function trainingPlanState(env, owner, runId, cancel = false, isConfigured = () => true) {
  const db = env.DB;
  const mapConfig = mapTrainingConfiguration(env);
  const now = Math.floor(Date.now() / 1000);
  if (cancel) {
    await db.prepare(`UPDATE training_plans SET cancelled_at=?
      WHERE owner_id=? AND id=? AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL AND expires_at>?`)
      .bind(now, owner, runId, now).run();
  }
  const row = await db.prepare(`SELECT fingerprint, plan_json, expires_at, cancelled_at, dispatch_claimed_at, dispatch_rejection,
      cleanup_confirmed_at
    FROM training_plans WHERE owner_id=? AND id=?`).bind(owner, runId).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const authorization = await getTrainingAuthorization(db, owner, runId, row.fingerprint);
  const state = row.cancelled_at !== null ? "cancelled"
    : row.dispatch_rejection ? "blocked"
    : row.dispatch_claimed_at !== null ? "dispatching" : row.expires_at <= now ? "expired" : "prepared";
  const authorized = state === "prepared" && authorization?.authorized_at !== null &&
    authorization?.authorized_at !== undefined && authorization?.expires_at > now &&
    authorization?.consumed_at === null;
  let plan = {};
  try { plan = JSON.parse(row.plan_json); } catch {}
  const mcpSubmitAuthorization = supportsMcpTrainingSubmit(plan);
  const ownerSelected = plan.execution_kind === "owner_selected_python";
  const admission = ownerSelected ? ownerTrainingAdmissionEnabled(env) : mapConfig.admission_enabled;
  const providerConfigured = isConfigured(env);
  const budgetPolicy = state === "prepared" ? await readProviderBudgetPolicy(db) : null;
  const monthlyLimit = ownerSelected ? plan.monthly_budget_microusd : mapConfig.monthly_microusd;
  const budgetAssessment = budgetPolicy ? assessModalTrainingBudget(budgetPolicy, {
    maxCostMicrousd: plan.max_cost_microusd, monthlyLimitMicrousd: monthlyLimit,
    requireRemaining: true, requireGpuAdmission: true,
  }) : null;
  const modalPolicyReady = budgetAssessment?.policyAvailable === true;
  const gpuAdmissionReady = budgetAssessment?.gpuAdmissionEnabled === true;
  const budgetWithinPolicy = budgetAssessment?.limitsSatisfied === true;
  const submitAdmissionReady = admission && gpuAdmissionReady && budgetWithinPolicy;
  const readinessBlocker = state !== "prepared" ? null
    : !modalPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE"
    : !gpuAdmissionReady ? "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED"
    : !budgetWithinPolicy ? "TRAINING_BUDGET_EXCEEDS_MODAL_PROVIDER_POLICY"
    : !admission ? (ownerSelected ? "OWNER_TRAINING_ADMISSION_DISABLED" : "MAP_TRAINING_ADMISSION_DISABLED")
    : !providerConfigured ? "TRAINING_PROVIDER_ADAPTER_NOT_CONFIGURED" : null;
  return { schema_version: 2, status: "ok",
    human_summary: readinessBlocker === "OWNER_TRAINING_ADMISSION_DISABLED"
      ? "保存済み計画は確認できましたが、owner-selected GPUの受付は停止中です。"
      : readinessBlocker === "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED"
      ? "Modal GPUの共通受付ポリシーが停止中です。"
      : readinessBlocker === "PROVIDER_BUDGET_POLICY_UNAVAILABLE"
      ? "Modal計算ルート共通の予算ポリシーを確認できません。"
      : readinessBlocker === "TRAINING_PROVIDER_ADAPTER_NOT_CONFIGURED"
      ? "保存済み計画は確認できましたが、実行アダプターが設定されていません。"
      : "保存済みの学習計画の状態です。",
    machine_state: { run_id: runId, state, plan_fingerprint: row.fingerprint,
      expires_at: row.expires_at, cancelled_at: row.cancelled_at,
      cleanup_state: row.dispatch_claimed_at === null ? "not_required"
        : row.cleanup_confirmed_at !== null ? "confirmed" : "unknown",
      authorization_state: state !== "prepared" ? "none" : !submitAdmissionReady ? "unavailable" : authorized ? "authorized" : "required",
      ...(!mcpSubmitAuthorization && submitAdmissionReady && providerConfigured && !authorized && state === "prepared"
        ? { authorization_url: trainingAuthorizationUrl(runId, row.fingerprint) } : {}),
      ...(row.dispatch_rejection ? { reason: row.dispatch_rejection } : {}) },
    next_allowed_actions: state === "prepared"
      ? [...(submitAdmissionReady && providerConfigured && (authorized || mcpSubmitAuthorization) ? ["training_submit"] : []), "training_cancel"] : [],
    blocking_reason: readinessBlocker };
}

export async function confirmTrainingCleanup(db, owner, runId, fingerprint, state, cleanup, now) {
  if (!["succeeded", "failed", "cancelled"].includes(state) || cleanup !== "confirmed") return false;
  const result = await db.prepare(`UPDATE training_plans SET cleanup_confirmed_at=COALESCE(cleanup_confirmed_at, ?)
    WHERE owner_id=? AND id=? AND fingerprint=? AND dispatch_claimed_at IS NOT NULL`)
    .bind(now, owner, runId, fingerprint).run();
  return (result?.meta?.changes ?? result?.changes ?? 0) > 0;
}

