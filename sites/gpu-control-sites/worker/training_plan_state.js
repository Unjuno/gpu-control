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
      cleanup_confirmed_at, provider_result_json
    FROM training_plans WHERE owner_id=? AND id=?`).bind(owner, runId).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const providerResult = readProviderResult(row.provider_result_json);
  const authorization = await getTrainingAuthorization(db, owner, runId, row.fingerprint);
  const state = providerResult && row.cleanup_confirmed_at !== null ? providerResult.state
    : row.cancelled_at !== null ? "cancelled"
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
  const nextAllowedActions = providerResult && row.cleanup_confirmed_at !== null
    ? [...(providerResult.state === "succeeded" ? ["training_checkpoint",
      ...(Array.isArray(providerResult.artifacts) && providerResult.artifacts.length ? ["training_artifact"] : [])]
      : providerResult.failure_code === "TRAINING_RUNTIME_LIMIT" ? ["training_checkpoint"] : [])]
    : state === "prepared" ? [...(submitAdmissionReady && providerConfigured && (authorized || mcpSubmitAuthorization) ? ["training_submit"] : []), "training_cancel"] : [];
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
    machine_state: { run_id: runId, state, execution_kind: plan.execution_kind || "map_training",
      plan_fingerprint: row.fingerprint,
      expires_at: row.expires_at, cancelled_at: row.cancelled_at,
      cleanup_state: row.dispatch_claimed_at === null ? "not_required"
        : row.cleanup_confirmed_at !== null ? "confirmed" : "unknown",
      ...(providerResult && row.cleanup_confirmed_at !== null ? providerResult : {}),
      authorization_state: state !== "prepared" ? "none" : !submitAdmissionReady ? "unavailable" : authorized ? "authorized" : "required",
      ...(!mcpSubmitAuthorization && submitAdmissionReady && providerConfigured && !authorized && state === "prepared"
        ? { authorization_url: trainingAuthorizationUrl(runId, row.fingerprint) } : {}),
      ...(row.dispatch_rejection ? { reason: row.dispatch_rejection } : {}) },
    next_allowed_actions: nextAllowedActions,
    blocking_reason: readinessBlocker };
}

function readProviderResult(value) {
  if (typeof value !== "string" || value.length > 65536) return null;
  try {
    const result = JSON.parse(value);
    return result && ["succeeded", "failed", "cancelled"].includes(result.state) &&
      (result.cleanup === "confirmed" || result.cleanup_state === "confirmed") ? {
        ...result, cleanup: "confirmed",
      } : null;
  } catch { return null; }
}

export async function loadApprovedTrainingPlan(db, owner, runId, fingerprint) {
  const row = await db.prepare(`SELECT plan_json, fingerprint, dispatch_claimed_at
    FROM training_plans WHERE owner_id=? AND id=?`).bind(owner, runId).first();
  if (!row || row.fingerprint !== fingerprint || row.dispatch_claimed_at === null) {
    throw new Error("RUN_NOT_FOUND");
  }
  let plan;
  try { plan = JSON.parse(row.plan_json); } catch { throw new Error("TRAINING_PLAN_INVALID"); }
  if (!plan || typeof plan !== "object" || Array.isArray(plan)) throw new Error("TRAINING_PLAN_INVALID");
  return { ...plan, run_id: runId };
}

const TERMINAL_TRAINING_STATES = new Set(["succeeded", "failed", "cancelled"]);
const PERSISTED_PROVIDER_RESULT_FIELDS = ["state", "execution_kind", "exit_code", "gpu_used", "gpu", "checkpoint", "metrics",
  "artifacts", "cleanup", "failure_code", "output", "output_truncated", "steps", "dataset", "run_name",
  "source_sha", "image_digest"];

function validDigest(value) {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}

function validCheckpoint(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    value.filename === "checkpoint.pt" && Number.isInteger(value.size_bytes) &&
    value.size_bytes > 0 && value.size_bytes <= 1024 ** 3 && validDigest(value.sha256);
}

function validMapCheckpoint(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    /^step-[0-9]{9}-[a-f0-9]{8}\.pt$/.test(value.filename || "") &&
    Number.isInteger(value.size_bytes) && value.size_bytes > 0 && value.size_bytes <= 1024 ** 3 &&
    validDigest(value.sha256);
}

function validMetrics(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    value.filename === "metrics.json" && Number.isInteger(value.size_bytes) &&
    value.size_bytes > 0 && value.size_bytes <= 8192 && validDigest(value.sha256) &&
    value.values && typeof value.values === "object" && !Array.isArray(value.values) &&
    Object.keys(value.values).length > 0 && Object.keys(value.values).length <= 64;
}

async function validArtifacts(value) {
  if (!Array.isArray(value) || value.length > 14) return false;
  for (const item of value) {
    if (!item || typeof item !== "object" || Array.isArray(item) ||
        typeof item.path !== "string" || !item.path.startsWith("artifacts/") ||
        item.path.split("/").some((part) => !part || part === "." || part === ".." ||
          !/^[A-Za-z0-9_.-]+$/.test(part)) ||
        typeof item.artifact_id !== "string" || !validDigest(item.artifact_id) ||
        !Number.isInteger(item.size_bytes) || item.size_bytes < 1 || item.size_bytes > 256 * 1024 * 1024 ||
        !validDigest(item.sha256)) return false;
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(item.path));
    const artifactId = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    if (item.artifact_id !== artifactId) return false;
  }
  return true;
}

export async function persistTrainingTerminalResult(db, owner, runId, fingerprint, result, now) {
  if (!result || !TERMINAL_TRAINING_STATES.has(result.state) || result.cleanup !== "confirmed") return false;
  const mapTraining = result.execution_kind === "map_training";
  if (result.exit_code !== undefined && result.exit_code !== null &&
      (!Number.isInteger(result.exit_code) || result.exit_code < 0 || result.exit_code > 255)) return false;
  if (result.gpu_used !== undefined && typeof result.gpu_used !== "boolean") return false;
  if (result.failure_code !== undefined && result.failure_code !== null &&
      (typeof result.failure_code !== "string" || result.failure_code.length > 128)) return false;
  if (result.output !== undefined && typeof result.output !== "string") return false;
  if (result.output_truncated !== undefined && typeof result.output_truncated !== "boolean") return false;
  if (result.artifacts !== undefined && !await validArtifacts(result.artifacts)) return false;
  if (result.state === "succeeded" && (result.gpu_used !== true ||
      (mapTraining
        ? (typeof result.steps !== "number" || !Number.isInteger(result.steps) || result.steps < 1 ||
          result.steps > 10_000_000 || !validMapCheckpoint(result.checkpoint) ||
          result.metrics !== undefined || (result.artifacts !== undefined && !await validArtifacts(result.artifacts)))
        : (result.exit_code !== 0 || !validCheckpoint(result.checkpoint) || !validMetrics(result.metrics) ||
          !await validArtifacts(result.artifacts))))) return false;
  const bounded = Object.fromEntries(PERSISTED_PROVIDER_RESULT_FIELDS
    .filter((key) => Object.hasOwn(result, key)).map((key) => [key, result[key]]));
  if (typeof bounded.output === "string" && new TextEncoder().encode(bounded.output).byteLength > 8192) return false;
  if (Object.hasOwn(bounded, "gpu") && bounded.gpu !== null) {
    const gpu = bounded.gpu;
    if (!gpu || typeof gpu !== "object" || Array.isArray(gpu) ||
        typeof gpu.name !== "string" || gpu.name.length > 256 ||
        !Array.isArray(gpu.capability) || gpu.capability.length !== 2 ||
        gpu.capability.some((part) => !Number.isInteger(part) || part < 0 || part > 100) ||
        gpu.cuda !== null && (typeof gpu.cuda !== "string" || gpu.cuda.length > 32)) return false;
    bounded.gpu = { name: gpu.name, capability: gpu.capability, cuda: gpu.cuda ?? null };
  }
  let json;
  try { json = JSON.stringify(bounded); } catch { return false; }
  if (typeof json !== "string" || new TextEncoder().encode(json).byteLength > 65536) return false;
  const saved = await db.prepare(`UPDATE training_plans SET
      provider_result_json=COALESCE(provider_result_json, ?),
      cleanup_confirmed_at=COALESCE(cleanup_confirmed_at, ?)
    WHERE owner_id=? AND id=? AND fingerprint=? AND dispatch_claimed_at IS NOT NULL
      AND (provider_result_json IS NULL OR provider_result_json=?)`)
    .bind(json, now, owner, runId, fingerprint, json).run();
  return (saved?.meta?.changes ?? saved?.changes ?? 0) > 0;
}
