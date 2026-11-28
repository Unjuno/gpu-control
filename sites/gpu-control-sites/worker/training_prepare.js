import { authorizeTrainingMcpSubmit, getTrainingAuthorization, trainingAuthorizationUrl } from "./training_authorization.js";
import { assessModalTrainingBudget, readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { MAP_TRAINING_MAX_MONTHLY_MICROUSD, OWNER_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { ownerTrainingAdmissionEnabled, ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { previewTrainingPlan } from "./training_preview.js";
import { sha256Hex } from "./sha256.js";

/** Persist the exact preview plan under the owner's idempotency key. */
export async function prepareTrainingPlan(env, owner, args, getSourceToken = async () => null, isConfigured = () => true) {
  const mapConfig = mapTrainingConfiguration(env);
  const { idempotency_key: key, ...inputs } = args;
  const preview = await previewTrainingPlan(env, owner, inputs, getSourceToken);
  if (preview.status !== "ok") return preview;

  const { executable, ...plan } = preview.machine_state;
  const json = JSON.stringify(plan);
  const fingerprint = await sha256Hex(JSON.stringify([owner, json]));
  const now = Math.floor(Date.now() / 1000);
  const expires = Math.min(now + 600, plan.quote_expires_at);
  if (expires <= now) throw new Error("TRAINING_PLAN_EXPIRED");
  await env.DB.prepare(`INSERT INTO training_plans
    (id, owner_id, registration_id, idempotency_key, fingerprint, plan_json, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(owner_id, idempotency_key) DO NOTHING`)
    .bind(crypto.randomUUID().replaceAll("-", ""), owner, plan.registration_id, key, fingerprint, json, now, expires).run();
  const existing = await env.DB.prepare(`SELECT id, fingerprint, expires_at, cancelled_at, dispatch_claimed_at FROM training_plans
    WHERE owner_id=? AND idempotency_key=?`).bind(owner, key).first();
  if (existing?.fingerprint !== fingerprint) throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  if (existing.expires_at <= now) throw new Error("TRAINING_PLAN_EXPIRED");
  const state = existing.cancelled_at !== null ? "cancelled"
    : existing.dispatch_claimed_at !== null ? "dispatching" : "prepared";
  const authorization = await getTrainingAuthorization(env.DB, owner, existing.id, fingerprint);
  const authorized = state === "prepared" && authorization?.authorized_at !== null &&
    authorization?.authorized_at !== undefined && authorization?.expires_at > now &&
    authorization?.consumed_at === null;
  const ownerSelected = plan.execution_kind === "owner_selected_python";
  const ownerConfig = ownerTrainingExecutionConfig(env);
  const admission = ownerSelected
    ? ownerTrainingAdmissionEnabled(env) &&
      ownerConfig.max_runtime_seconds >= plan.runtime_seconds
    : mapConfig.admission_enabled &&
      mapConfig.runtime_seconds === plan.runtime_seconds;
  const actions = state === "prepared" ? ["training_status", "training_cancel"] : ["training_status"];
  // Owner-selected plans are authorized by the exact destructive MCP submit
  // call. The connected host presents its native confirmation once for that run.
  const providerConfigured = isConfigured(env);
  const currentBudgetPolicy = await readProviderBudgetPolicy(env.DB);
  const planMonthlyBudget = plan.monthly_budget_microusd ?? mapConfig.monthly_microusd;
  const gpuBudgetReady = assessModalTrainingBudget(currentBudgetPolicy, { maxCostMicrousd: plan.max_cost_microusd,
    monthlyLimitMicrousd: planMonthlyBudget, requireGpuAdmission: true }).ready;
  const executableNow = state === "prepared" && admission && gpuBudgetReady && providerConfigured &&
    (authorized || ownerSelected);
  if (executableNow) actions.unshift("training_submit");
  return { ...preview, approved_plan: plan, next_allowed_actions: actions,
    human_summary: !admission
      ? "学習計画は保存しましたが、現在この条件の実行受付は停止中です。"
      : !gpuBudgetReady
      ? "Modal GPUの共通受付またはアカウント予算ポリシーを確認できないため、送信できません。"
      : !providerConfigured
      ? "学習計画は保存しましたが、実行アダプターが設定されていません。"
      : authorized
      ? "学習計画を保存しました。所有者確認済みなので、このplanを送信できます。"
      : ownerSelected
      ? "学習計画を保存しました。このMCPクライアントから送信するときに、固定commit・GPU・予算上限を1回だけ確認します。"
      : "学習計画を保存しました。送信前にauthorization_urlを開き、このplanの有料実行を確認してください。Modalへのログインは不要です。",
    machine_state: { ...plan, executable: executableNow, run_id: existing.id,
      plan_fingerprint: fingerprint, idempotency_key: key, expires_at: existing.expires_at, state,
      authorization_state: !admission || !gpuBudgetReady ? "unavailable" : authorized ? "authorized" : "required",
      ...(admission && gpuBudgetReady && providerConfigured && !authorized && state === "prepared" && !ownerSelected
        ? { authorization_url: trainingAuthorizationUrl(existing.id, fingerprint) } : {}) } };
}

