import { findOwnedTrainingSource, getOwnedTrainingSource, MAP_TRAINING_REPOSITORY } from "./training_source.js";
import { authorizeTrainingMcpSubmit, getTrainingAuthorization, trainingAuthorizationUrl } from "./training_authorization.js";
import { trainingRuntimeProfileFingerprint } from "./training_contract.js";
import { previewModalOwnerTrainingPlan } from "./modal_owner_training_plan.js";
import { previewMapTrainingPlan } from "./map_training_plan.js";
import { readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { claimTrainingDispatch } from "./training_dispatch_claim.js";
import { trainingPlanState } from "./training_plan_state.js";
import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { MAP_TRAINING_MAX_COST_MICROUSD, MAP_TRAINING_MAX_MONTHLY_MICROUSD,
  MAP_TRAINING_MAX_RUNTIME_SECONDS, MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
  OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { ownerTrainingAdmissionEnabled, ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { trainingControlPlaneSha } from "./training_security_configuration.js";
import { canonicalJson as canonical } from "./canonical_json.js";
import { sha256Hex } from "./sha256.js";

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
  if (source.repository === MAP_TRAINING_REPOSITORY) return previewMapTrainingPlan(env, owner, args, source);
  return previewModalOwnerTrainingPlan(env, args, source, getSourceToken);
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
  // Owner-selected plans are authorized by the exact destructive MCP submit
  // call. The connected host presents its native confirmation once for that run.
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
      ? "学習計画を保存しました。このMCPクライアントから送信するときに、固定commit・GPU・予算上限を1回だけ確認します。"
      : "学習計画を保存しました。送信前にauthorization_urlを開き、このplanの有料実行を確認してください。Modalへのログインは不要です。",
    machine_state: { ...plan, executable: executableNow, run_id: existing.id,
      plan_fingerprint: fingerprint, idempotency_key: key, expires_at: existing.expires_at, state,
      authorization_state: !admission || !gpuBudgetReady ? "unavailable" : authorized ? "authorized" : "required",
      ...(admission && gpuBudgetReady && providerConfigured && !authorized && state === "prepared" && !ownerSelected
        ? { authorization_url: trainingAuthorizationUrl(existing.id, fingerprint) } : {}) } };
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
  const controlPlaneSha = trainingControlPlaneSha(env);
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
    const authorized = await authorizeTrainingMcpSubmit(env.DB, owner, runId, fingerprint,
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
      ? "このMCPのplan実行確認を安全に記録できませんでした。計算は開始していません。"
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
