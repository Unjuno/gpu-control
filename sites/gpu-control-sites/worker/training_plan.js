import { findOwnedTrainingSource, getOwnedTrainingSource, MAP_TRAINING_REPOSITORY } from "./training_source.js";
import { authorizeTrainingChatSubmit, getTrainingAuthorization } from "./training_authorization.js";
import { readPublicTrainingContract, trainingRuntimeProfileFingerprint } from "./training_contract.js";
import { prepareModalComputeBudgetReservation, readProviderBudgetPolicy, utcMonthKey } from "./provider_budget_policy.js";
import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { DEFAULT_MAP_EXECUTION, MAP_TRAINING_MAX_COST_MICROUSD, MAP_TRAINING_MAX_MONTHLY_MICROUSD,
  MAP_TRAINING_MAX_RUNTIME_SECONDS, MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
  OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { ownerTrainingAdmissionEnabled, ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { canonicalJson as canonical } from "./canonical_json.js";
import { sha256Hex } from "./sha256.js";

const SITE_PUBLIC_ORIGIN = "https://gpu-control-sites.unjuno.chatgpt.site";
const MAX_PRICING_AGE_SECONDS = 30 * 24 * 60 * 60;

function trainingAuthorizationUrl(runId, fingerprint) {
  const url = new URL("/authorize-training", SITE_PUBLIC_ORIGIN);
  url.searchParams.set("run_id", runId);
  url.searchParams.set("plan_fingerprint", fingerprint);
  return url.toString();
}

function validMapExecution(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).sort().join(",") === "dataset,run_name,steps" &&
    typeof value.dataset === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value.dataset) &&
    typeof value.run_name === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value.run_name) &&
    Number.isSafeInteger(value.steps) && value.steps >= 1 && value.steps <= 100000;
}

async function previewOwnerTrainingPlan(env, owner, args, source, getSourceToken) {
  const config = ownerTrainingExecutionConfig(env);
  const { image_id: imageId, hourly_microusd: rate, staging_hourly_microusd: stagingRate,
    quote_expires_at: quoteExpires, max_runtime_seconds: maxRuntime, max_cost_microusd: maxCost,
    monthly_microusd: monthly } = config;
  const controlPlaneSha = config.control_plane_sha;
  let contract;
  try {
    const token = await getSourceToken(source.repository);
    contract = await readPublicTrainingContract(source.repository, source.commit, fetch, token, config);
  } catch (error) {
    return { schema_version: 2, status: "blocked",
      human_summary: "GitHubの固定commitから実験manifestとdependency lockを読めませんでした。",
      machine_state: { ...source, execution_available: false }, next_allowed_actions: [],
      blocking_reason: error?.message?.startsWith("TRAINING_") ? error.message : "TRAINING_GITHUB_LOOKUP_FAILED" };
  }
  const inspected = { ...source, ...contract };
  if (!contract.execution_available) return { schema_version: 2, status: "blocked",
    human_summary: "このcommitは確認できましたが、GPU実行条件が揃っていません。",
    machine_state: inspected, next_allowed_actions: [],
    blocking_reason: contract.execution_blocking_reason };
  if (typeof controlPlaneSha !== "string" || !/^[0-9a-f]{40}$/.test(controlPlaneSha)) {
    return { schema_version: 2, status: "blocked",
      human_summary: "現在のGPU Control commitをplanへ固定できません。",
      machine_state: inspected, next_allowed_actions: [],
      blocking_reason: "TRAINING_AUTHORIZATION_NOT_CONFIGURED" };
  }
  const runtime = args.runtime_seconds;
  const budget = args.max_cost_microusd;
  if (!Number.isSafeInteger(runtime) || runtime < 120 || runtime > maxRuntime ||
      !Number.isSafeInteger(budget) || budget < 1 || budget > maxCost || budget > 1_000_000) {
    return { schema_version: 2, status: "blocked",
      human_summary: "指定した実行時間または費用上限が、このowner-selected GPU枠を超えています。",
      machine_state: { ...inspected, max_runtime_seconds: maxRuntime, max_cost_ceiling_microusd: maxCost },
      next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_OR_RUNTIME_INVALID" };
  }
  const now = Math.floor(Date.now() / 1000);
  const stagingRuntime = 300;
  const estimatedCost = Math.ceil((rate * (runtime + 300) + stagingRate * stagingRuntime) / 3240);
  if (estimatedCost > budget) return { schema_version: 2, status: "blocked",
    human_summary: "この費用上限ではModal GPUと起動時間の見積もりをカバーできません。",
    machine_state: { ...inspected, estimated_cost_microusd: estimatedCost },
    next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_LOW" };
  const gpu = contract.manifest.gpu_profiles.find((profile) => ["T4", "L4"].includes(profile));
  const executionSpecId = (await sha256Hex(`${source.registration_id}:${contract.manifest_sha256}:${contract.dependency_lock.sha256}`)).slice(0, 32);
  if (args.execution_spec_id !== undefined && args.execution_spec_id !== executionSpecId) {
    return { schema_version: 2, status: "blocked",
      human_summary: "この固定commitとmanifestに一致するexecution specがありません。",
      machine_state: source, next_allowed_actions: [], blocking_reason: "TRAINING_CONFIGURATION_NOT_FOUND" };
  }
  const lockSha = contract.dependency_lock.sha256;
  return { schema_version: 2, status: "ok",
    human_summary: "GitHubの固定commit、GPU profile、依存lock、実行時間、費用上限を確認しました。",
    machine_state: { execution_kind: "owner_selected_python", registration_id: source.registration_id,
      execution_spec_id: args.execution_spec_id || executionSpecId,
      repository: source.repository, commit: source.commit, control_plane_sha: controlPlaneSha,
      manifest: contract.manifest, manifest_sha256: contract.manifest_sha256,
      dependencies_lock: contract.manifest.dependencies_lock, lock_sha256: lockSha,
      command: ["python", contract.manifest.entrypoint], image_id: imageId, image_digest: imageId,
      provider: "modal", provider_resource_id: "gpu-control-provider-adapter/owner_training",
      gpu, gpu_count: 1, runtime_seconds: runtime, max_cost_microusd: budget,
      hourly_microusd: rate, staging_hourly_microusd: stagingRate,
      staging_runtime_seconds: stagingRuntime, staging_cpu_cores: 1, staging_memory_mib: 1024,
      quote_expires_at: quoteExpires, estimated_cost_microusd: estimatedCost,
      monthly_budget_microusd: monthly,
      task: contract.manifest.task, executable: false },
    next_allowed_actions: [], blocking_reason: null };
}

export async function previewTrainingPlan(env, owner, args, getSourceToken = async () => null) {
  const ownerConfig = ownerTrainingExecutionConfig(env);
  const mapConfig = mapTrainingConfiguration(env);
  const source = args.registration_id
    ? await getOwnedTrainingSource(env.DB, owner, args.registration_id)
    : await findOwnedTrainingSource(env.DB, owner, args);
  // Keep the simple chat path simple: a registered source can be previewed
  // and prepared with only its registration ID. MAP keeps its reviewed fixed
  // bounds; an owner-selected source defaults to a short run and the
  // independently configured per-run ceiling. The caller may narrow either.
  if (source.repository === MAP_TRAINING_REPOSITORY) {
    args = { ...args,
      runtime_seconds: args.runtime_seconds ?? MAP_TRAINING_MAX_RUNTIME_SECONDS,
      max_cost_microusd: args.max_cost_microusd ?? MAP_TRAINING_MAX_COST_MICROUSD };
  } else {
    const configuredRuntime = ownerConfig.max_runtime_seconds;
    const configuredCost = ownerConfig.max_cost_microusd;
    args = { ...args,
      runtime_seconds: args.runtime_seconds ?? Math.min(Number.isSafeInteger(configuredRuntime) ? configuredRuntime : 300, 300),
      max_cost_microusd: args.max_cost_microusd ?? Math.min(Number.isSafeInteger(configuredCost)
        ? configuredCost : OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_COST_MICROUSD) };
  }
  const budgetPolicy = await readProviderBudgetPolicy(env.DB);
  const modalBudget = budgetPolicy.provider_budgets.find((item) => item.provider === "modal");
  if (budgetPolicy.state !== "ready" || !modalBudget) return { schema_version: 2, status: "blocked",
    human_summary: "Modal計算ルート共通の予算ポリシーを確認できないため、計画を作成できません。",
    machine_state: { repository: source.repository, commit: source.commit,
      provider_budget_policy_state: "unavailable" },
    next_allowed_actions: ["experiment_capabilities"], blocking_reason: "PROVIDER_BUDGET_POLICY_UNAVAILABLE" };
  const laneMonthlyLimit = source.repository === MAP_TRAINING_REPOSITORY
    ? mapConfig.monthly_microusd
    : ownerConfig.monthly_microusd;
  const laneMonthlyMaximum = source.repository === MAP_TRAINING_REPOSITORY
    ? MAP_TRAINING_MAX_MONTHLY_MICROUSD : OWNER_TRAINING_MAX_MONTHLY_MICROUSD;
  if (!Number.isSafeInteger(args.max_cost_microusd) || args.max_cost_microusd < 1 ||
      args.max_cost_microusd > modalBudget.per_run_limit_microusd ||
      args.max_cost_microusd > modalBudget.monthly_remaining_microusd ||
      !Number.isSafeInteger(laneMonthlyLimit) || laneMonthlyLimit < 1 ||
      laneMonthlyLimit > laneMonthlyMaximum || laneMonthlyLimit > modalBudget.monthly_limit_microusd) return { schema_version: 2, status: "blocked",
    human_summary: "指定された実験上限がModal計算ルート共通の1回または月次上限を超えています。",
    machine_state: { provider: "modal", per_run_limit_usd: modalBudget.per_run_limit_usd,
      monthly_limit_usd: modalBudget.monthly_limit_usd },
    next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_EXCEEDS_MODAL_PROVIDER_POLICY" };
  if (source.repository !== MAP_TRAINING_REPOSITORY) return previewOwnerTrainingPlan(env, owner, args, source, getSourceToken);
  if (args.runtime_seconds !== MAP_TRAINING_MAX_RUNTIME_SECONDS) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの1回あたりの実行時間上限は120秒です。",
    machine_state: { max_runtime_seconds: MAP_TRAINING_MAX_RUNTIME_SECONDS },
    next_allowed_actions: [], blocking_reason: "TRAINING_RUNTIME_TOO_HIGH" };
  const machine = { ...source, executable: false };
  let execution = DEFAULT_MAP_EXECUTION;
  let executionSpecId = args.execution_spec_id;
  if (!executionSpecId) {
    const { results = [] } = await env.DB.prepare(`SELECT id AS execution_spec_id, spec_json
      FROM training_execution_specs WHERE owner_id=? AND registration_id=?
      ORDER BY created_at DESC, id DESC LIMIT 2`).bind(owner, source.registration_id).all();
    if (results.length > 1) return { schema_version: 2, status: "blocked",
      human_summary: "このソースには複数の学習設定があります。training_listから実行設定を選んでください。",
      machine_state: { ...machine, execution_specs: results.map(({ execution_spec_id, spec_json }) => ({
        execution_spec_id, ...JSON.parse(spec_json),
      })) }, next_allowed_actions: [], blocking_reason: "TRAINING_CONFIGURATION_SELECTION_REQUIRED" };
    if (results.length === 1) {
      executionSpecId = results[0].execution_spec_id;
      execution = JSON.parse(results[0].spec_json);
    }
  } else {
    const spec = await env.DB.prepare(`SELECT spec_json FROM training_execution_specs
      WHERE owner_id=? AND registration_id=? AND id=?`)
      .bind(owner, source.registration_id, executionSpecId).first();
    if (!spec) throw new Error("TRAINING_REGISTRATION_NOT_FOUND");
    execution = JSON.parse(spec.spec_json);
  }
  if (!validMapExecution(execution)) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの学習設定が不正です。登録済み設定を確認してください。",
    machine_state: { ...machine, ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
    next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_INVALID" };
  if (!Number.isSafeInteger(args.max_cost_microusd) || args.max_cost_microusd < 1 ||
      args.max_cost_microusd > MAP_TRAINING_MAX_COST_MICROUSD) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの1回あたりの費用上限は$0.25です。",
    machine_state: { ...machine, ...execution,
      ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      max_cost_ceiling_microusd: MAP_TRAINING_MAX_COST_MICROUSD },
    next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_HIGH" };
  const imageId = mapConfig.image_id;
  const imageIdentity = imageId || mapConfig.image_digest;
  const imagePattern = imageId ? /^im-[A-Za-z0-9]{8,128}$/ : /^sha256:[0-9a-f]{64}$/;
  // These values are set by the operator after reviewing the commit and building
  // the image. A registration alone never gives a commit execution authority.
  if (source.repository !== MAP_TRAINING_REPOSITORY ||
      source.commit !== mapConfig.source_sha ||
      !imagePattern.test(imageIdentity || "")) {
    return { schema_version: 2, status: "blocked",
      human_summary: "このコミットに対応する検証済みの学習イメージが設定されていません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
      next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_UNAVAILABLE" };
  }
  const now = Math.floor(Date.now() / 1000);
  const hourlyRate = mapConfig.hourly_microusd;
  const quoteExpires = mapConfig.quote_expires_at;
  if (!Number.isSafeInteger(hourlyRate) || hourlyRate <= 0 || hourlyRate > 1000000000 ||
      !Number.isSafeInteger(quoteExpires) || quoteExpires <= now || quoteExpires > now + MAX_PRICING_AGE_SECONDS) {
    return { schema_version: 2, status: "blocked",
      human_summary: "有効な学習料金の見積もりが設定されていません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
      next_allowed_actions: [], blocking_reason: "TRAINING_QUOTE_UNAVAILABLE" };
  }
  // The source app allows up to 600 seconds of startup. Reserve that
  // separately and apply the source policy's 10 percent budget margin.
  const estimatedCost = Math.ceil(hourlyRate * (args.runtime_seconds + 600) / 3240);
  if (estimatedCost > args.max_cost_microusd) {
    return { schema_version: 2, status: "blocked",
      human_summary: "指定された予算上限では、この実行時間の見積もりをカバーできません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
        estimated_cost_microusd: estimatedCost },
      next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_LOW" };
  }
  const accountEvidence = await readModalGpuAccountEvidence(env, {
    key: "MAP_TRAINING_ACCOUNT_EVIDENCE_JSON", gpu: "L4",
    usageLimitUsd: MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
    expectedHourlyMicrousd: hourlyRate,
    requiredHeadroomMicrousd: args.max_cost_microusd + 10_000,
    now,
  });
  if (!accountEvidence) return { schema_version: 2, status: "blocked",
    human_summary: "MAPのL4価格またはModal Workspaceの利用額・$1上限の短期証拠が未設定、期限切れ、または不一致です。GPUは起動していません。",
    machine_state: { ...machine, ...execution, account_evidence_valid: false, gpu_started: false },
    next_allowed_actions: [], blocking_reason: "MAP_TRAINING_ACCOUNT_EVIDENCE_REQUIRED" };
  return { schema_version: 2, status: "ok",
    human_summary: "MAP-44Mの学習条件を確認しました。実行計画を準備できます。",
    machine_state: { ...machine, ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      ...execution, image_digest: imageIdentity, provider: "modal",
      provider_resource_id: "gpu-control-map-training/train_map",
      gpu: "L4", gpu_count: 1, runtime_seconds: args.runtime_seconds,
      estimated_cost_microusd: estimatedCost, hourly_microusd: hourlyRate, quote_expires_at: quoteExpires,
      max_cost_microusd: args.max_cost_microusd, provider_evidence: accountEvidence,
      workspace_usage_limit_usd: MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
      checkpoint_visibility: "owner_private" },
    next_allowed_actions: [], blocking_reason: null };
}

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
  // Owner-selected plans are authorized by the exact destructive ChatGPT MCP
  // submit call. The host presents its native confirmation once for that run.
  const providerConfigured = isConfigured(env);
  const currentBudgetPolicy = await readProviderBudgetPolicy(env.DB);
  const modalBudget = currentBudgetPolicy.provider_budgets.find((item) => item.provider === "modal");
  const planMonthlyBudget = plan.monthly_budget_microusd ?? mapConfig.monthly_microusd;
  const gpuBudgetReady = currentBudgetPolicy.state === "ready" &&
    modalBudget?.modal_gpu_admission_enabled === true &&
    plan.max_cost_microusd <= modalBudget.per_run_limit_microusd &&
    Number.isSafeInteger(planMonthlyBudget) && planMonthlyBudget <= modalBudget.monthly_limit_microusd;
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
      ? "学習計画を保存しました。ChatGPTから送信するときに、この固定commit・GPU・予算上限を1回だけ確認します。"
      : "学習計画を保存しました。送信前にauthorization_urlを開き、このplanの有料実行を確認してください。Modalへのログインは不要です。",
    machine_state: { ...plan, executable: executableNow, run_id: existing.id,
      plan_fingerprint: fingerprint, idempotency_key: key, expires_at: existing.expires_at, state,
      authorization_state: !admission || !gpuBudgetReady ? "unavailable" : authorized ? "authorized" : "required",
      ...(admission && gpuBudgetReady && providerConfigured && !authorized && state === "prepared" && !ownerSelected
        ? { authorization_url: trainingAuthorizationUrl(existing.id, fingerprint) } : {}) } };
}

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
  const ownerSelected = plan.execution_kind === "owner_selected_python";
  const admission = ownerSelected ? ownerTrainingAdmissionEnabled(env) : mapConfig.admission_enabled;
  const providerConfigured = isConfigured(env);
  const siteConfirmationRequired = !ownerSelected;
  const budgetPolicy = state === "prepared" ? await readProviderBudgetPolicy(db) : null;
  const modalBudget = budgetPolicy?.provider_budgets.find((item) => item.provider === "modal");
  const monthlyLimit = ownerSelected ? plan.monthly_budget_microusd : mapConfig.monthly_microusd;
  const modalPolicyReady = budgetPolicy?.state === "ready" && modalBudget;
  const gpuAdmissionReady = modalBudget?.modal_gpu_admission_enabled === true;
  const budgetWithinPolicy = modalPolicyReady && Number.isSafeInteger(plan.max_cost_microusd) &&
    plan.max_cost_microusd <= modalBudget.per_run_limit_microusd && Number.isSafeInteger(monthlyLimit) &&
    monthlyLimit <= modalBudget.monthly_limit_microusd &&
    plan.max_cost_microusd <= modalBudget.monthly_remaining_microusd;
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
      ...(siteConfirmationRequired && submitAdmissionReady && providerConfigured && !authorized && state === "prepared"
        ? { authorization_url: trainingAuthorizationUrl(runId, row.fingerprint) } : {}),
      ...(row.dispatch_rejection ? { reason: row.dispatch_rejection } : {}) },
    next_allowed_actions: state === "prepared"
      ? [...(submitAdmissionReady && providerConfigured && (authorized || ownerSelected) ? ["training_submit"] : []), "training_cancel"] : [],
    blocking_reason: readinessBlocker };
}

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

export async function confirmTrainingCleanup(db, owner, runId, fingerprint, state, cleanup, now) {
  if (!["succeeded", "failed", "cancelled"].includes(state) || cleanup !== "confirmed") return false;
  const result = await db.prepare(`UPDATE training_plans SET cleanup_confirmed_at=COALESCE(cleanup_confirmed_at, ?)
    WHERE owner_id=? AND id=? AND fingerprint=? AND dispatch_claimed_at IS NOT NULL`)
    .bind(now, owner, runId, fingerprint).run();
  return (result?.meta?.changes ?? result?.changes ?? 0) > 0;
}

export async function submitTrainingPlan(env, owner, args, delegate, isConfigured, getSourceToken = async () => null) {
  const { run_id: runId, plan_fingerprint: fingerprint, approved_plan: approved } = args;
  const row = await env.DB.prepare(`SELECT plan_json, dispatch_claimed_at, expires_at FROM training_plans
    WHERE owner_id=? AND id=? AND fingerprint=?`).bind(owner, runId, fingerprint).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const plan = JSON.parse(row.plan_json);
  const { admission_token: _admissionToken, ...approvedPlan } = approved;
  if (canonical(approvedPlan, "INVALID_ARGUMENTS") !== canonical(plan, "INVALID_ARGUMENTS")) {
    throw new Error("INVALID_ARGUMENTS");
  }
  if (row.dispatch_claimed_at !== null) return trainingPlanState(env, owner, runId);
  const controlPlaneSha = env.MAP_TRAINING_CONTROL_PLANE_SHA;
  if (typeof controlPlaneSha !== "string" || !/^[0-9a-f]{40}$/.test(controlPlaneSha)) {
    return { schema_version: 2, status: "blocked", human_summary: "学習の認証境界が設定されていません。",
      machine_state: { run_id: runId }, next_allowed_actions: ["training_status"],
      blocking_reason: "TRAINING_AUTHORIZATION_NOT_CONFIGURED" };
  }
  const ownerSelected = plan.execution_kind === "owner_selected_python";
  const ownerConfig = ownerTrainingExecutionConfig(env);
  const mapConfig = mapTrainingConfiguration(env);
  {
    const budgetPolicy = await readProviderBudgetPolicy(env.DB);
    const modalProviderPolicy = budgetPolicy.provider_budgets.find((item) => item.provider === "modal");
    if (budgetPolicy.state !== "ready" || !modalProviderPolicy) return { schema_version: 2, status: "blocked",
      human_summary: "Modal GPUの予算ポリシーを確認できないため、実験は開始していません。",
      machine_state: { run_id: runId, provider_budget_policy_state: "unavailable" },
      next_allowed_actions: ["experiment_capabilities", "training_status"],
      blocking_reason: "PROVIDER_BUDGET_POLICY_UNAVAILABLE" };
    if (modalProviderPolicy.modal_gpu_admission_enabled !== true) return { schema_version: 2, status: "blocked",
      human_summary: "Modal GPUのD1受付ポリシーが停止中です。予算予約と実験開始は行っていません。",
      machine_state: { run_id: runId, provider: "modal_gpu", budget_admission_enabled: false },
      next_allowed_actions: ["experiment_capabilities", "training_status"],
      blocking_reason: "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED" };
    if (!Number.isSafeInteger(plan.max_cost_microusd) ||
        plan.max_cost_microusd > modalProviderPolicy.per_run_limit_microusd ||
        !Number.isSafeInteger(ownerSelected ? plan.monthly_budget_microusd : mapConfig.monthly_microusd) ||
        (ownerSelected ? plan.monthly_budget_microusd : mapConfig.monthly_microusd) > modalProviderPolicy.monthly_limit_microusd) return { schema_version: 2, status: "blocked",
      human_summary: "実験上限がModal計算ルート共通の予算上限を超えています。",
      machine_state: { run_id: runId, provider: "modal", budget_policy_available: true },
      next_allowed_actions: ["experiment_capabilities", "training_status"],
      blocking_reason: "TRAINING_BUDGET_EXCEEDS_MODAL_PROVIDER_POLICY" };
  }
  const admissionEnabled = ownerSelected
    ? ownerTrainingAdmissionEnabled(env)
    : mapConfig.admission_enabled;
  if (!admissionEnabled || !isConfigured(env)) {
    return { schema_version: 2, status: "blocked", human_summary: "学習の実行受付は停止中です。",
      machine_state: { run_id: runId }, next_allowed_actions: [], blocking_reason: "TRAINING_ADMISSION_DISABLED" };
  }
  const configuredRuntime = ownerSelected
    ? ownerConfig.max_runtime_seconds
    : mapConfig.runtime_seconds;
  if (ownerSelected ? configuredRuntime < plan.runtime_seconds
    : configuredRuntime !== plan.runtime_seconds) {
    return { schema_version: 2, status: "blocked",
      human_summary: "計画の時間上限がModalに設定された上限と一致しません。",
      machine_state: { run_id: runId }, next_allowed_actions: [], blocking_reason: "TRAINING_RUNTIME_MISMATCH" };
  }
  const sourceToken = ownerSelected ? await getSourceToken(plan.repository) : null;
  if (!ownerSelected) {
    const accountEvidence = await readModalGpuAccountEvidence(env, {
      key: "MAP_TRAINING_ACCOUNT_EVIDENCE_JSON", gpu: "L4",
      usageLimitUsd: MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
      expectedHourlyMicrousd: plan.hourly_microusd,
      requiredHeadroomMicrousd: plan.max_cost_microusd + 10_000,
      now: Math.floor(Date.now() / 1000),
    });
    if (!accountEvidence || accountEvidence.evidence_id !== plan.provider_evidence?.evidence_id) {
      return { schema_version: 2, status: "blocked",
        human_summary: "Modal Workspace利用証拠がplan作成後に期限切れ、変更、または上限不一致になりました。実験は開始していません。",
        machine_state: { run_id: runId, account_evidence_valid: false, gpu_started: false },
        next_allowed_actions: ["training_prepare"],
        blocking_reason: "MAP_TRAINING_ACCOUNT_EVIDENCE_STALE_OR_MISMATCHED" };
    }
  }
  const current = await previewTrainingPlan(env, owner, plan, async () => sourceToken);
  const { executable, ...currentPlan } = current.machine_state;
  if (current.status !== "ok" || canonical(currentPlan, "INVALID_ARGUMENTS") !== canonical(plan, "INVALID_ARGUMENTS")) {
    throw new Error("TRAINING_PLAN_EXPIRED");
  }
  if (ownerSelected) {
    // Recheck the adapter-owned execution gates immediately before reserving
    // monthly budget or consuming the one-use authorization. Capabilities are
    // read-only; they do not start a provider workload.
    let adapterReadiness;
    try {
      const capabilities = await delegate(env, owner, "experiment_capabilities", {});
      adapterReadiness = capabilities?.machine_state?.owner_selected_training;
    } catch {
      adapterReadiness = null;
    }
    const profileFingerprint = await trainingRuntimeProfileFingerprint(ownerTrainingExecutionConfig(env));
    if (!adapterReadiness || adapterReadiness.profile_configured !== true ||
        adapterReadiness.control_plane_configured !== true ||
        adapterReadiness.admission_enabled !== true ||
        adapterReadiness.profile_fingerprint !== profileFingerprint) {
      const adapterGatesOpen = adapterReadiness?.profile_configured === true &&
        adapterReadiness?.control_plane_configured === true && adapterReadiness?.admission_enabled === true;
      const profileMismatch = Boolean(adapterGatesOpen && profileFingerprint &&
        adapterReadiness.profile_fingerprint !== profileFingerprint);
      return { schema_version: 2, status: "blocked",
        human_summary: "Modalアダプターの実行設定を確認できないか、Sites側と一致しません。予算予約と実験開始は行っていません。",
        machine_state: { run_id: runId, adapter_readiness_available: Boolean(adapterReadiness) },
        next_allowed_actions: ["experiment_capabilities", "training_status"],
        blocking_reason: profileMismatch ? "OWNER_TRAINING_ADAPTER_PROFILE_MISMATCH"
          : adapterReadiness?.blocker || "OWNER_TRAINING_ADAPTER_READINESS_UNAVAILABLE" };
    }
  }
  const now = Math.floor(Date.now() / 1000);
  let authorization = await getTrainingAuthorization(env.DB, owner, runId, fingerprint);
  if (ownerSelected && (!authorization || authorization.expires_at <= now || authorization.consumed_at !== null)) {
    const authorized = await authorizeTrainingChatSubmit(env.DB, owner, runId, fingerprint,
      controlPlaneSha, now);
    if (authorized) authorization = await getTrainingAuthorization(env.DB, owner, runId, fingerprint);
  }
  const validAuthorizationSource = ownerSelected
    ? ["site_owner_plan_confirmation", "chatgpt_mcp_write_confirmation"].includes(authorization?.authorization_source)
    : authorization?.authorization_source === "site_owner_plan_confirmation";
  const expectedAuthorization = authorization && validAuthorizationSource &&
    authorization.authorized_by === owner && authorization.control_plane_sha === controlPlaneSha &&
    authorization.decision_record_id === `training-plan:${runId}:${fingerprint}` &&
    authorization.target_repository === plan.repository && authorization.target_sha === plan.commit &&
    authorization.image_digest === plan.image_digest && authorization.provider === plan.provider &&
    authorization.provider_resource_id === plan.provider_resource_id && authorization.gpu_count === plan.gpu_count &&
    authorization.runtime_seconds === plan.runtime_seconds && authorization.max_cost_microusd === plan.max_cost_microusd &&
    authorization.authorized_at !== null && authorization.expires_at > now && authorization.consumed_at === null;
  if (!expectedAuthorization) return { schema_version: 2, status: "blocked",
    human_summary: ownerSelected
      ? "ChatGPTのこのplan確認を安全に記録できませんでした。計算は開始していません。"
      : "このplanはまだSite上で有料実行の確認が済んでいません。authorization_urlを開いて確認してください。",
    machine_state: { run_id: runId, authorization_state: "required",
      ...(!ownerSelected ? { authorization_url: trainingAuthorizationUrl(runId, fingerprint) } : {}) },
    next_allowed_actions: ["training_status"],
    blocking_reason: "TRAINING_AUTHORIZATION_REQUIRED" };
  // Mint the read-only GitHub App token only after owner, exact plan, and
  // execution authorization are verified. It is forwarded only to the trusted
  // source stager and is never written to the D1 plan or run record.
  const monthlyLimit = ownerSelected
    ? ownerConfig.monthly_microusd
    : mapConfig.monthly_microusd;
  const claimed = await claimTrainingDispatch(env.DB, owner, runId, fingerprint, now,
    monthlyLimit, authorization, ownerSelected ? OWNER_TRAINING_MAX_MONTHLY_MICROUSD : MAP_TRAINING_MAX_MONTHLY_MICROUSD,
    { source: ownerSelected ? "owner_selected_training" : "map_training",
      requestedMicrousd: plan.max_cost_microusd });
  if (!claimed) {
    const active = await env.DB.prepare(`SELECT id FROM training_plans WHERE owner_id=? AND id<>?
      AND dispatch_claimed_at IS NOT NULL AND dispatch_rejection IS NULL AND cleanup_confirmed_at IS NULL
      ORDER BY dispatch_claimed_at LIMIT 1`).bind(owner, runId).first();
    return { schema_version: 2, status: "blocked",
      human_summary: active ? "前の実験がcleanup確認待ちです。同じrunのstatusを確認します。"
        : "計画または予算枠を確保できませんでした。",
      machine_state: { run_id: runId, ...(active ? { active_run_id: active.id } : {}) },
      next_allowed_actions: ["training_status"],
      blocking_reason: active ? "TRAINING_PREVIOUS_RUN_CLEANUP_REQUIRED" : "TRAINING_DISPATCH_NOT_RESERVED" };
  }
  const delegatedAuthorization = {
    authorization_id: authorization.authorization_id,
    authorization_source: authorization.authorization_source,
    authorization_reference: authorization.authorization_reference,
    decision_record_id: authorization.decision_record_id,
    authorized_by: authorization.authorized_by,
    control_plane_sha: authorization.control_plane_sha,
    target_repository: authorization.target_repository,
    target_sha: authorization.target_sha,
    image_digest: authorization.image_digest,
    provider: authorization.provider,
    provider_resource_id: authorization.provider_resource_id,
    gpu_count: authorization.gpu_count,
    runtime_seconds: authorization.runtime_seconds,
    max_cost_microusd: authorization.max_cost_microusd,
    authorized_at: authorization.authorized_at,
    expires_at: authorization.expires_at,
    owner,
    run_id: runId,
    plan_fingerprint: fingerprint,
  };
  let state = "uncertain";
  try {
    const response = await delegate(env, owner, "training_submit", {
      run_id: runId, plan_fingerprint: fingerprint, plan: { ...plan, run_id: runId },
      authorization: delegatedAuthorization,
      authorization_expires_at: authorization.expires_at,
      ...(sourceToken ? { source_token: sourceToken } : {}),
    });
    if (response?.state === "blocked" &&
        ["TRAINING_ADMISSION_DISABLED", "TRAINING_AUTHORIZATION_EXPIRED"].includes(response.reason)) {
      await env.DB.prepare(`UPDATE training_plans SET dispatch_rejection=?
        WHERE owner_id=? AND id=? AND fingerprint=? AND dispatch_claimed_at IS NOT NULL`)
        .bind(response.reason, owner, runId, fingerprint).run();
      return { schema_version: 2, status: "blocked",
        human_summary: "プロバイダーは学習の受付を拒否しました。",
        machine_state: { run_id: runId, state: "blocked" },
        next_allowed_actions: ["training_status"], blocking_reason: response.reason };
    }
    if (["running", "staging"].includes(response?.state)) state = response.state;
  } catch {
    // The provider may have accepted the call. Recover by status, never respawn.
  }
  return { schema_version: 2, status: "pending", human_summary: "学習の送信状態を確認してください。",
    machine_state: { run_id: runId, state }, next_allowed_actions: ["training_status"], blocking_reason: null };
}
