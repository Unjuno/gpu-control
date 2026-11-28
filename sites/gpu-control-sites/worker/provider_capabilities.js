import { githubAppConfigured, getOwnedGithubInstallation } from "./github_app_connection.js";
import { callProviderAdapterTool, providerAdapterConfigured } from "./provider_adapter_client.js";
import { readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { trainingControlPlaneConfigured, trainingRuntimeProfileConfigured,
  trainingRuntimeProfileFingerprint } from "./training_contract.js";
import { ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { runpodConfigured } from "./runpod_provider.js";
import { RUNPOD_WORKLOAD } from "./runpod_plan.js";
import { WORKLOADS } from "./workload_registry.js";
import { MODAL_MAX_RUNTIME_SECONDS, MODAL_PRICING_CHECKED_AT, MODAL_PRICING_SOURCE,
  MODAL_SANDBOX_COST_CEILING_USD, MODAL_SANDBOX_RESOURCES, estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";

const WORKLOAD = WORKLOADS.tiny_stories.id;
const KAGGLE_WORKLOAD = WORKLOADS.kaggle_training.id;
const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_WORKLOAD = WORKLOADS.modal_gpu_canary.id;

async function humanAuthorizationStoreReady(env) {
  try {
    const row = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='human_authorizations'").first();
    return row?.name === "human_authorizations";
  } catch {
    return false;
  }
}

function workloadCapabilityEntries(env, enabledByWorkloadId) {
  const byId = new Map(Object.values(WORKLOADS).map((workload) => [workload.id, workload]));
  // Keep the established response order stable; newly registered workloads
  // remain visible, but are appended and disabled until explicitly supported.
  const orderedIds = [WORKLOAD, RUNPOD_WORKLOAD, MODAL_GPU_WORKLOAD, KAGGLE_WORKLOAD, ZERO_GPU_WORKLOAD];
  const workloads = [
    ...orderedIds.map((id) => byId.get(id)).filter(Boolean),
    ...[...byId.values()].filter((workload) => !orderedIds.includes(workload.id)),
  ];
  return workloads.map((workload) => {
    const capability = {
      id: workload.id,
      name: workload.display_name,
      providers: [workload.provider],
      enabled: enabledByWorkloadId.get(workload.id) === true,
      provider: workload.provider,
      requires_gpu: workload.requires_gpu,
      max_runtime_seconds: workload.runtime_seconds,
      max_cost_usd: workload.cost_ceiling_usd,
      cancellation: workload.cancellation,
    };
    if (workload.id === WORKLOAD) {
      capability.sandbox_resources = { ...MODAL_SANDBOX_RESOURCES };
      capability.estimated_max_sandbox_cost_usd = estimateModalSandboxCostUsd(workload.runtime_seconds);
      capability.image_digest = env.CPU_WORKLOAD_IMAGE_DIGEST || null;
    } else if (workload.id === RUNPOD_WORKLOAD) {
      capability.image = env.RUNPOD_WORKLOAD_IMAGE || null;
    } else if (workload.id === MODAL_GPU_WORKLOAD) {
      capability.gpu = workload.adapter_manifest.gpu;
    } else if ([KAGGLE_WORKLOAD, ZERO_GPU_WORKLOAD].includes(workload.id)) {
      capability.paid_fallback_allowed = false;
    }
    return capability;
  });
}

export async function getExperimentCapabilities(env, owner, { modalConfigured }) {
  if (!env.DB) return { available: false, blocker: "D1_NOT_CONFIGURED", providers: [], workloads: [] };
  const budgetPolicy = await readProviderBudgetPolicy(env.DB);
  const providerBudgets = budgetPolicy.provider_budgets;
  const modalProviderBudget = providerBudgets.find((item) => item.provider === "modal");
  const providerBudgetPolicyReady = budgetPolicy.state === "ready";
  const authorizationStoreReady = await humanAuthorizationStoreReady(env);
  const providerConfigured = modalConfigured(env);
  const runpodProviderConfigured = runpodConfigured(env);
  const runpodCompletionTransportVerified = env.RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED === "true";
  const runpodEnabled = env.RUNPOD_WORKLOAD_ADMISSION_ENABLED === "true" &&
    runpodProviderConfigured && authorizationStoreReady && runpodCompletionTransportVerified && providerBudgetPolicyReady;
  // Capabilities is read-only. Defer the billable live health probe until submit,
  // after the exact plan's one-use human authorization has been verified.
  const modalCpuBudgetAvailable = Number.isSafeInteger(modalProviderBudget?.monthly_remaining_microusd) &&
    modalProviderBudget.monthly_remaining_microusd >= 10_000;
  const available = env.CPU_WORKLOAD_ADMISSION_ENABLED === "true" && providerConfigured && authorizationStoreReady &&
    providerBudgetPolicyReady && modalCpuBudgetAvailable;
  const enabledByWorkloadId = new Map([
    [WORKLOAD, available],
    [RUNPOD_WORKLOAD, runpodEnabled],
  ]);
  const result = {
    schema_version: 2,
    status: "ok",
    human_summary: available
      ? "Capabilitiesを確認しました。Modal CPUは1 core / 512 MiB、最大30秒です。実際の接続確認はplan確認後に行います。Sandbox使用料は利用可能なクレジットがあれば充当されます。"
      : "Capabilitiesを確認しました。Modal CPU routeは停止中です。他provider/workloadの可否は各enabledとblockerを参照してください。",
    machine_state: { available, provider_configured: providerConfigured, provider_ready: null, provider_health_checks: { configured: providerConfigured, deferred_until_authorized_submit: true }, human_authorization_store_ready: authorizationStoreReady, explicit_plan_confirmation_required: true, admission_enabled: env.CPU_WORKLOAD_ADMISSION_ENABLED === "true", provider: "modal_cpu", workload: WORKLOAD, free: false, paid: true, credit_eligible: true, max_runtime_seconds: MODAL_MAX_RUNTIME_SECONDS, max_inflight: 1, sandbox_resources: { ...MODAL_SANDBOX_RESOURCES }, estimated_max_sandbox_cost_usd: estimateModalSandboxCostUsd(MODAL_MAX_RUNTIME_SECONDS), max_sandbox_cost_ceiling_usd: MODAL_SANDBOX_COST_CEILING_USD, control_function_cost_included: false, price_source: MODAL_PRICING_SOURCE, price_checked_at: MODAL_PRICING_CHECKED_AT, image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT || null },
    blocking_reason: available ? null : (!providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE" :
      !modalCpuBudgetAvailable ? "PROVIDER_BUDGET_EXHAUSTED" :
      !authorizationStoreReady ? "HUMAN_AUTHORIZATION_STORAGE_NOT_CONFIGURED" :
      !providerConfigured ? "MODAL_PROVIDER_NOT_CONFIGURED" : "CPU_WORKLOAD_ADMISSION_DISABLED"),
    providers: [
      { id: "modal_cpu", enabled: available, configured: providerConfigured, free: false, paid: true, credit_eligible: true },
      { id: "modal_gpu", enabled: false, configured: false, free: false, paid: true,
        credit_eligible: true, gpu_count: 1, blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED",
        budget_scope: modalProviderBudget?.scope ?? null,
        monthly_limit_usd: modalProviderBudget?.monthly_limit_usd ?? null,
        per_run_limit_usd: modalProviderBudget?.per_run_limit_usd ?? null },
      { id: "runpod_gpu", enabled: runpodEnabled, configured: runpodProviderConfigured, free: false, paid: true,
        credit_eligible: false, gpu_count: 1, api_version: "v2", execution_interface: "registered_workload_only",
        completion_transport_verified: runpodCompletionTransportVerified,
        blocker: runpodEnabled ? null : (!providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE" :
          !runpodProviderConfigured ? "RUNPOD_PROVIDER_NOT_CONFIGURED" :
          !runpodCompletionTransportVerified ? "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED" :
          "RUNPOD_WORKLOAD_ADMISSION_DISABLED") },
      { id: "kaggle", enabled: false, configured: false, free: true, paid: false,
        paid_fallback_allowed: false, blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED" },
      { id: "huggingface_space", enabled: false, configured: false, free: true, paid: false,
        paid_fallback_allowed: false, blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED" },
    ],
    workloads: workloadCapabilityEntries(env, enabledByWorkloadId),
    provider_budget_policy_state: budgetPolicy.state,
    provider_budgets: providerBudgets,
    paid_execution: "parked",
  };
  const githubConfigured = githubAppConfigured(env);
  let githubConnected = false;
  if (githubConfigured) {
    try { githubConnected = Boolean(await getOwnedGithubInstallation(env.DB, owner)); }
    catch { githubConnected = false; }
  }
  const ownerTrainingAdmission = env.OWNER_TRAINING_ADMISSION_ENABLED === "true";
  const ownerTrainingAdapterConfigured = providerAdapterConfigured(env);
  const ownerTrainingConfig = ownerTrainingExecutionConfig(env);
  const ownerTrainingSiteProfileConfigured = trainingRuntimeProfileConfigured(ownerTrainingConfig);
  const ownerTrainingSiteControlPlaneConfigured = trainingControlPlaneConfigured(env.MAP_TRAINING_CONTROL_PLANE_SHA);
  const ownerTrainingSiteProfileFingerprint = await trainingRuntimeProfileFingerprint(ownerTrainingExecutionConfig(env));
  const ownerTrainingBudgetAvailable = Number.isSafeInteger(ownerTrainingConfig.monthly_microusd) &&
    ownerTrainingConfig.monthly_microusd > 0 &&
    ownerTrainingConfig.monthly_microusd <= OWNER_TRAINING_MAX_MONTHLY_MICROUSD &&
    ownerTrainingConfig.monthly_microusd <= (modalProviderBudget?.monthly_limit_microusd ?? 0) &&
    (modalProviderBudget?.monthly_remaining_microusd ?? 0) > 0 &&
    Number.isSafeInteger(ownerTrainingConfig.max_cost_microusd) &&
    ownerTrainingConfig.max_cost_microusd > 0 && ownerTrainingConfig.max_cost_microusd <= OWNER_TRAINING_MAX_COST_MICROUSD &&
    ownerTrainingConfig.max_cost_microusd <= (modalProviderBudget?.per_run_limit_microusd ?? 0);
  const ownerTrainingCapability = {
    execution_kind: "owner_selected_python",
    compute_provider: "modal_gpu",
    repository_access: "authenticated_owner_selected_github_repositories",
    requires_manifest: ".gpu-control/experiment.json",
    requires_hash_locked_dependencies: true,
    registration_id_is_internal: true,
    ask_user_for_registration_id: false,
    github_app_configured: githubConfigured,
    github_connected: githubConnected,
    adapter_configured: ownerTrainingAdapterConfigured,
    site_profile_configured: ownerTrainingSiteProfileConfigured,
    site_control_plane_configured: ownerTrainingSiteControlPlaneConfigured,
    admission_enabled: ownerTrainingAdmission,
    provider_budget_policy_ready: providerBudgetPolicyReady,
    provider_budget_admission_enabled: modalProviderBudget?.modal_gpu_admission_enabled === true,
    budget_policy: ownerTrainingBudgetAvailable ? {
      state: "ready", provider: "modal", scope: "modal_compute_shared_across_routes",
      monthly_limit_usd: modalProviderBudget.monthly_limit_usd,
      per_run_limit_usd: modalProviderBudget.per_run_limit_usd,
    } : { state: "unavailable", provider: "modal", scope: "modal_compute_shared_across_routes" },
    adapter_readiness_available: false,
    adapter_profile_configured: false,
    adapter_control_plane_configured: false,
    adapter_admission_enabled: false,
    adapter_profile_matches: false,
    ready_to_prepare: false,
    paid_fallback_allowed: false,
    next_actions: !githubConfigured
      ? ["github_connection_status"]
      : !githubConnected
      ? ["github_connection_start"]
      : ["github_repositories", "training_register", "training_preview",
        "training_list"],
    blocker: !githubConfigured ? "GITHUB_APP_NOT_CONFIGURED"
      : !githubConnected ? "GITHUB_CONNECTION_REQUIRED"
      : !ownerTrainingAdapterConfigured ? "PROVIDER_ADAPTER_NOT_CONFIGURED" : "OWNER_TRAINING_ADAPTER_READINESS_UNAVAILABLE",
  };
  result.machine_state.owner_selected_training = ownerTrainingCapability;
  if (!providerAdapterConfigured(env)) {
    result.provider_adapter = { configured: false, available: false, blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED" };
    return result;
  }
  try {
    const delegated = await callProviderAdapterTool(env, owner, "experiment_capabilities", {});
    const adapterOwnerTraining = delegated?.machine_state?.owner_selected_training;
    ownerTrainingCapability.adapter_readiness_available = Boolean(adapterOwnerTraining &&
      typeof adapterOwnerTraining === "object" && !Array.isArray(adapterOwnerTraining));
    ownerTrainingCapability.adapter_profile_configured = adapterOwnerTraining?.profile_configured === true;
    ownerTrainingCapability.adapter_control_plane_configured = adapterOwnerTraining?.control_plane_configured === true;
    ownerTrainingCapability.adapter_admission_enabled = adapterOwnerTraining?.admission_enabled === true;
    ownerTrainingCapability.adapter_profile_matches = Boolean(ownerTrainingSiteProfileFingerprint &&
      adapterOwnerTraining?.profile_fingerprint === ownerTrainingSiteProfileFingerprint);
    ownerTrainingCapability.ready_to_prepare = githubConfigured && githubConnected &&
      ownerTrainingAdapterConfigured && ownerTrainingSiteProfileConfigured && ownerTrainingSiteControlPlaneConfigured &&
      ownerTrainingAdmission && ownerTrainingCapability.adapter_profile_configured &&
      ownerTrainingCapability.adapter_control_plane_configured && ownerTrainingCapability.adapter_admission_enabled &&
      ownerTrainingCapability.adapter_profile_matches && providerBudgetPolicyReady &&
      modalProviderBudget?.modal_gpu_admission_enabled === true && ownerTrainingBudgetAvailable;
    ownerTrainingCapability.blocker = !githubConfigured ? "GITHUB_APP_NOT_CONFIGURED"
      : !githubConnected ? "GITHUB_CONNECTION_REQUIRED"
      : !ownerTrainingAdapterConfigured ? "PROVIDER_ADAPTER_NOT_CONFIGURED"
      : !ownerTrainingSiteProfileConfigured ? "OWNER_TRAINING_SITE_PROFILE_NOT_CONFIGURED"
      : !ownerTrainingCapability.adapter_readiness_available ? "OWNER_TRAINING_ADAPTER_CAPABILITY_UNAVAILABLE"
      : !ownerTrainingCapability.adapter_profile_configured ? "OWNER_TRAINING_ADAPTER_PROFILE_NOT_CONFIGURED"
      : !ownerTrainingSiteControlPlaneConfigured || !ownerTrainingCapability.adapter_control_plane_configured
        ? "TRAINING_AUTHORIZATION_NOT_CONFIGURED"
      : !ownerTrainingAdmission || !ownerTrainingCapability.adapter_admission_enabled
        ? "OWNER_TRAINING_ADMISSION_DISABLED"
      : !providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE"
      : modalProviderBudget?.modal_gpu_admission_enabled !== true ? "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED"
      : !ownerTrainingBudgetAvailable ? "OWNER_TRAINING_BUDGET_POLICY_UNAVAILABLE"
      : !ownerTrainingCapability.adapter_profile_matches ? "OWNER_TRAINING_ADAPTER_PROFILE_MISMATCH" : null;
    const { profile_fingerprint: _profileFingerprint, ...safeAdapterOwnerTraining } = adapterOwnerTraining || {};
    const safeDelegated = { ...delegated,
      provider_budget_policy_state: budgetPolicy.state,
      provider_budgets: providerBudgets,
      machine_state: { ...delegated.machine_state,
        owner_selected_training: adapterOwnerTraining ? safeAdapterOwnerTraining : adapterOwnerTraining } };
    result.provider_adapter = { configured: true, available: true, capabilities: safeDelegated };
    if (ownerTrainingCapability.ready_to_prepare) {
      ownerTrainingCapability.next_actions = ["github_repositories", "training_register",
        "training_preview", "training_prepare", "training_list"];
    }
    const adapterProviders = Array.isArray(delegated?.machine_state?.providers)
      ? delegated.machine_state.providers : [];
    const adapterWorkloads = new Map([
      ["kaggle", KAGGLE_WORKLOAD],
      ["huggingface_space", ZERO_GPU_WORKLOAD],
      ["modal_gpu", MODAL_GPU_WORKLOAD],
    ]);
    for (const [providerId, workloadId] of adapterWorkloads) {
      const adapterProvider = adapterProviders.find((item) => item?.id === providerId);
      const provider = result.providers.find((item) => item.id === providerId);
      const budgetProvider = providerId === "modal_gpu" ? modalProviderBudget
        : providerBudgets.find((item) => item.provider === providerId);
      provider.configured = adapterProvider?.configured === true;
      provider.enabled = providerBudgetPolicyReady && provider.configured && adapterProvider?.paid_fallback === false &&
        (providerId !== "modal_gpu" || Number.isSafeInteger(budgetProvider?.monthly_remaining_microusd) &&
          budgetProvider.monthly_remaining_microusd >= 10_000 && env.MODAL_GPU_WORKLOAD_ADMISSION_ENABLED === "true" &&
          budgetProvider?.modal_gpu_admission_enabled === true);
      if (providerId === "modal_gpu" && budgetProvider) {
        provider.budget_scope = budgetProvider.scope;
        provider.monthly_limit_usd = budgetProvider.monthly_limit_usd;
        provider.per_run_limit_usd = budgetProvider.per_run_limit_usd;
      }
      provider.blocker = provider.enabled ? null : (!providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE" : providerId === "modal_gpu"
        ? (!provider.configured ? "MODAL_GPU_PROVIDER_NOT_CONFIGURED"
          : (budgetProvider?.monthly_remaining_microusd ?? 0) < 10_000 ? "PROVIDER_BUDGET_EXHAUSTED"
            : "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED")
        : "FREE_PROVIDER_NOT_CONFIGURED");
      const workload = result.workloads.find((item) => item.id === workloadId);
      if (workload) workload.enabled = provider.enabled;
    }
  } catch {
    result.provider_adapter = { configured: true, available: false, blocker: "PROVIDER_ADAPTER_UNAVAILABLE" };
    ownerTrainingCapability.blocker = "OWNER_TRAINING_ADAPTER_READINESS_UNAVAILABLE";
  }
  return result;
}

