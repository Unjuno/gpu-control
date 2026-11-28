import { githubAppConfigured, getOwnedGithubInstallation } from "./github_app_connection.js";
import { callProviderAdapterTool, providerAdapterConfigured } from "./provider_adapter_client.js";
import { trainingControlPlaneConfigured, trainingRuntimeProfileConfigured,
  trainingRuntimeProfileFingerprint } from "./training_contract.js";
import { ownerTrainingAdmissionEnabled, ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { trainingControlPlaneSha } from "./training_security_configuration.js";
import { OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { assessModalTrainingBudget } from "./provider_budget_policy.js";

export async function getOwnerTrainingCapability(env, owner, budgetPolicy) {
  const providerBudgets = budgetPolicy.provider_budgets;
  const runtimeConfig = ownerTrainingExecutionConfig(env);
  const modalBudgetAssessment = assessModalTrainingBudget(budgetPolicy, {
    maxCostMicrousd: runtimeConfig.max_cost_microusd,
    monthlyLimitMicrousd: runtimeConfig.monthly_microusd,
    monthlyMaximumMicrousd: OWNER_TRAINING_MAX_MONTHLY_MICROUSD,
  });
  const modalProviderBudget = modalBudgetAssessment.providerBudget;
  const providerBudgetPolicyReady = budgetPolicy.state === "ready";
  const githubConfigured = githubAppConfigured(env);
  let githubConnected = false;
  if (githubConfigured) {
    try { githubConnected = Boolean(await getOwnedGithubInstallation(env.DB, owner)); }
    catch { githubConnected = false; }
  }
  const admissionEnabled = ownerTrainingAdmissionEnabled(env);
  const adapterConfigured = providerAdapterConfigured(env);
  const siteProfileConfigured = trainingRuntimeProfileConfigured(runtimeConfig);
  const siteControlPlaneConfigured = trainingControlPlaneConfigured(trainingControlPlaneSha(env));
  const siteProfileFingerprint = await trainingRuntimeProfileFingerprint(ownerTrainingExecutionConfig(env));
  const budgetAvailable = modalBudgetAssessment.limitsSatisfied && modalBudgetAssessment.monthlyRemainingPositive &&
    runtimeConfig.max_cost_microusd <= OWNER_TRAINING_MAX_COST_MICROUSD;

  const capability = {
    execution_kind: "owner_selected_python",
    compute_provider: "modal_gpu",
    repository_access: "authenticated_owner_selected_github_repositories",
    requires_manifest: ".gpu-control/experiment.json",
    requires_hash_locked_dependencies: true,
    registration_id_is_internal: true,
    ask_user_for_registration_id: false,
    github_app_configured: githubConfigured,
    github_connected: githubConnected,
    adapter_configured: adapterConfigured,
    site_profile_configured: siteProfileConfigured,
    site_control_plane_configured: siteControlPlaneConfigured,
    admission_enabled: admissionEnabled,
    provider_budget_policy_ready: providerBudgetPolicyReady,
    provider_budget_admission_enabled: modalProviderBudget?.modal_gpu_admission_enabled === true,
    budget_policy: budgetAvailable ? {
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
      : ["github_repositories", "training_register", "training_preview", "training_list"],
    blocker: !githubConfigured ? "GITHUB_APP_NOT_CONFIGURED"
      : !githubConnected ? "GITHUB_CONNECTION_REQUIRED"
      : !adapterConfigured ? "PROVIDER_ADAPTER_NOT_CONFIGURED" : "OWNER_TRAINING_ADAPTER_READINESS_UNAVAILABLE",
  };

  if (!adapterConfigured) return { capability, adapter_configured: false, adapter_available: false };
  try {
    const delegated = await callProviderAdapterTool(env, owner, "experiment_capabilities", {});
    const adapterCapability = delegated?.machine_state?.owner_selected_training;
    capability.adapter_readiness_available = Boolean(adapterCapability &&
      typeof adapterCapability === "object" && !Array.isArray(adapterCapability));
    capability.adapter_profile_configured = adapterCapability?.profile_configured === true;
    capability.adapter_control_plane_configured = adapterCapability?.control_plane_configured === true;
    capability.adapter_admission_enabled = adapterCapability?.admission_enabled === true;
    capability.adapter_profile_matches = Boolean(siteProfileFingerprint &&
      adapterCapability?.profile_fingerprint === siteProfileFingerprint);
    capability.ready_to_prepare = githubConfigured && githubConnected && adapterConfigured &&
      siteProfileConfigured && siteControlPlaneConfigured && admissionEnabled &&
      capability.adapter_profile_configured && capability.adapter_control_plane_configured &&
      capability.adapter_admission_enabled && capability.adapter_profile_matches &&
      providerBudgetPolicyReady && modalProviderBudget?.modal_gpu_admission_enabled === true && budgetAvailable;
    capability.blocker = !githubConfigured ? "GITHUB_APP_NOT_CONFIGURED"
      : !githubConnected ? "GITHUB_CONNECTION_REQUIRED"
      : !adapterConfigured ? "PROVIDER_ADAPTER_NOT_CONFIGURED"
      : !siteProfileConfigured ? "OWNER_TRAINING_SITE_PROFILE_NOT_CONFIGURED"
      : !capability.adapter_readiness_available ? "OWNER_TRAINING_ADAPTER_CAPABILITY_UNAVAILABLE"
      : !capability.adapter_profile_configured ? "OWNER_TRAINING_ADAPTER_PROFILE_NOT_CONFIGURED"
      : !siteControlPlaneConfigured || !capability.adapter_control_plane_configured
        ? "TRAINING_AUTHORIZATION_NOT_CONFIGURED"
      : !admissionEnabled || !capability.adapter_admission_enabled
        ? "OWNER_TRAINING_ADMISSION_DISABLED"
      : !providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE"
      : modalProviderBudget?.modal_gpu_admission_enabled !== true ? "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED"
      : !budgetAvailable ? "OWNER_TRAINING_BUDGET_POLICY_UNAVAILABLE"
      : !capability.adapter_profile_matches ? "OWNER_TRAINING_ADAPTER_PROFILE_MISMATCH" : null;
    const { profile_fingerprint: _profileFingerprint, ...safeAdapterCapability } = adapterCapability || {};
    const safeDelegated = { ...delegated,
      provider_budget_policy_state: budgetPolicy.state,
      provider_budgets: providerBudgets,
      machine_state: { ...delegated.machine_state,
        owner_selected_training: adapterCapability ? safeAdapterCapability : adapterCapability } };
    if (capability.ready_to_prepare) {
      capability.next_actions = ["github_repositories", "training_register", "training_preview", "training_prepare", "training_list"];
    }
    return { capability, adapter_configured: true, adapter_available: true,
      adapter_capabilities: safeDelegated,
      adapter_providers: Array.isArray(delegated?.machine_state?.providers)
        ? delegated.machine_state.providers : [] };
  } catch {
    capability.blocker = "OWNER_TRAINING_ADAPTER_READINESS_UNAVAILABLE";
    return { capability, adapter_configured: true, adapter_available: false };
  }
}
