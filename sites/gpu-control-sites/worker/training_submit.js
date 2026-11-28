import { authorizeTrainingMcpSubmit, getTrainingAuthorization, trainingAuthorizationUrl } from "./training_authorization.js";
import { trainingRuntimeProfileFingerprint } from "./training_contract.js";
import { assessModalTrainingBudget, readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { claimTrainingDispatch } from "./training_dispatch_claim.js";
import { trainingPlanState } from "./training_plan_state.js";
import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { MAP_TRAINING_MAX_MONTHLY_MICROUSD, MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
  OWNER_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { ownerTrainingAdmissionEnabled, ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { trainingControlPlaneSha } from "./training_security_configuration.js";
import { canonicalJson as canonical } from "./canonical_json.js";
import { previewTrainingPlan } from "./training_preview.js";

/** Revalidate and dispatch one exact owner-bound plan without creating a replacement. */
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
    const trainingBudget = assessModalTrainingBudget(budgetPolicy, {
      maxCostMicrousd: plan.max_cost_microusd,
      monthlyLimitMicrousd: ownerSelected ? plan.monthly_budget_microusd : mapConfig.monthly_microusd,
      requireGpuAdmission: true,
    });
    if (!trainingBudget.policyAvailable) return { schema_version: 2, status: "blocked",
      human_summary: "Modal GPUの予算ポリシーを確認できないため、実験は開始していません。",
      machine_state: { run_id: runId, provider_budget_policy_state: "unavailable" },
      next_allowed_actions: ["experiment_capabilities", "training_status"],
      blocking_reason: "PROVIDER_BUDGET_POLICY_UNAVAILABLE" };
    if (!trainingBudget.gpuAdmissionEnabled) return { schema_version: 2, status: "blocked",
      human_summary: "Modal GPUのD1受付ポリシーが停止中です。予算予約と実験開始は行っていません。",
      machine_state: { run_id: runId, provider: "modal_gpu", budget_admission_enabled: false },
      next_allowed_actions: ["experiment_capabilities", "training_status"],
      blocking_reason: "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED" };
    if (!trainingBudget.limitsSatisfied) return { schema_version: 2, status: "blocked",
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
