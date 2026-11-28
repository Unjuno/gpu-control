import { readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { runpodConfigured } from "./runpod_provider.js";
import { RUNPOD_WORKLOAD } from "./runpod_plan.js";
import { WORKLOADS } from "./workload_registry.js";
import { PROVIDERS, PROVIDER_ROUTES } from "./provider_catalog.js";
import { MODAL_MAX_RUNTIME_SECONDS, MODAL_PRICING_CHECKED_AT, MODAL_PRICING_SOURCE,
  MODAL_SANDBOX_COST_CEILING_USD, MODAL_SANDBOX_RESOURCES, estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";
import { getOwnerTrainingCapability } from "./owner_training_capabilities.js";
import { googleColabConnectionConfigured, googleColabConnectionStatus } from "./google_colab_connection.js";
import { googleColabLifecycleConfigured } from "./google_colab_tools.js";
import { googleColabAdmissionEnabled } from "./google_colab_policy.js";

const WORKLOAD = WORKLOADS.tiny_stories.id;
const KAGGLE_WORKLOAD = WORKLOADS.kaggle_training.id;
const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_WORKLOAD = WORKLOADS.modal_gpu_canary.id;

function providerRouteCapability(route) {
  const provider = PROVIDERS[route.provider];
  const free = provider.billing_model === "included_quota" && provider.subscription_cost_outside_gpu_control !== true;
  const paid = provider.billing_model === "usage_billed";
  return {
    id: route.id,
    enabled: false,
    configured: false,
    free,
    paid,
    billing_model: provider.billing_model,
    ...(provider.quota_balance_available_via_api === false ? { quota_limited: true,
      exact_run_cost_available: false, subscription_cost_outside_gpu_control: true } : {}),
    credit_eligible: provider.credit_eligible,
    ...(route.gpu_count ? { gpu_count: route.gpu_count } : {}),
    ...(route.api_version ? { api_version: route.api_version } : {}),
    ...(route.execution_interface ? { execution_interface: route.execution_interface } : {}),
    ...(provider.paid_fallback_allowed === false ? { paid_fallback_allowed: false } : {}),
  };
}

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
  const modalProviderBudget = providerBudgets.find((item) => item.provider === PROVIDERS.modal.budget_provider);
  const providerBudgetPolicyReady = budgetPolicy.state === "ready";
  const authorizationStoreReady = await humanAuthorizationStoreReady(env);
  const providerConfigured = modalConfigured(env);
  const colabOAuthConfigured = googleColabConnectionConfigured(env);
  const colabConnected = colabOAuthConfigured && (await googleColabConnectionStatus(env.DB, owner)).connected;
  const colabLifecycleReady = colabConnected && await googleColabLifecycleConfigured(env);
  const colabAdmissionEnabled = googleColabAdmissionEnabled(env);
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
  const providers = Object.values(PROVIDER_ROUTES).map(providerRouteCapability);
  const providerByRoute = new Map(providers.map((provider) => [provider.id, provider]));
  Object.assign(providerByRoute.get(PROVIDER_ROUTES.modal_cpu.id), { enabled: available, configured: providerConfigured });
  Object.assign(providerByRoute.get(PROVIDER_ROUTES.modal_gpu.id), {
    blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED",
    budget_scope: modalProviderBudget?.scope ?? null,
    monthly_limit_usd: modalProviderBudget?.monthly_limit_usd ?? null,
    per_run_limit_usd: modalProviderBudget?.per_run_limit_usd ?? null,
  });
  Object.assign(providerByRoute.get(PROVIDER_ROUTES.runpod_gpu.id), {
    enabled: runpodEnabled,
    configured: runpodProviderConfigured,
    completion_transport_verified: runpodCompletionTransportVerified,
    blocker: runpodEnabled ? null : (!providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE" :
      !runpodProviderConfigured ? "RUNPOD_PROVIDER_NOT_CONFIGURED" :
      !runpodCompletionTransportVerified ? "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED" :
      "RUNPOD_WORKLOAD_ADMISSION_DISABLED"),
  });
  Object.assign(providerByRoute.get(PROVIDER_ROUTES.google_colab.id), {
    configured: colabOAuthConfigured && await googleColabLifecycleConfigured(env),
    connected: colabConnected,
    admission_enabled: colabAdmissionEnabled,
    enabled: colabLifecycleReady && colabAdmissionEnabled,
    exact_run_cost_available: false,
    compute_unit_balance_available_via_api: false,
    paid_fallback_allowed: false,
    blocker: colabLifecycleReady && colabAdmissionEnabled ? null : (!colabOAuthConfigured ? "GOOGLE_COLAB_OAUTH_NOT_CONFIGURED"
      : !colabConnected ? "GOOGLE_COLAB_CONNECTION_REQUIRED" : !colabLifecycleReady ? "COLAB_RUN_STORAGE_NOT_CONFIGURED"
        : "GOOGLE_COLAB_WORKLOAD_ADMISSION_DISABLED"),
  });
  for (const routeId of [PROVIDER_ROUTES.kaggle.id, PROVIDER_ROUTES.huggingface_space.id]) {
    Object.assign(providerByRoute.get(routeId), { blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED" });
  }
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
    machine_state: { available, provider_configured: providerConfigured, provider_ready: null, provider_health_checks: { configured: providerConfigured, deferred_until_authorized_submit: true }, human_authorization_store_ready: authorizationStoreReady, explicit_plan_confirmation_required: true, admission_enabled: env.CPU_WORKLOAD_ADMISSION_ENABLED === "true", provider: PROVIDER_ROUTES.modal_cpu.id, workload: WORKLOAD, free: false, paid: true, credit_eligible: true, max_runtime_seconds: MODAL_MAX_RUNTIME_SECONDS, max_inflight: 1, sandbox_resources: { ...MODAL_SANDBOX_RESOURCES }, estimated_max_sandbox_cost_usd: estimateModalSandboxCostUsd(MODAL_MAX_RUNTIME_SECONDS), max_sandbox_cost_ceiling_usd: MODAL_SANDBOX_COST_CEILING_USD, control_function_cost_included: false, price_source: MODAL_PRICING_SOURCE, price_checked_at: MODAL_PRICING_CHECKED_AT, image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT || null },
    blocking_reason: available ? null : (!providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE" :
      !modalCpuBudgetAvailable ? "PROVIDER_BUDGET_EXHAUSTED" :
      !authorizationStoreReady ? "HUMAN_AUTHORIZATION_STORAGE_NOT_CONFIGURED" :
      !providerConfigured ? "MODAL_PROVIDER_NOT_CONFIGURED" : "CPU_WORKLOAD_ADMISSION_DISABLED"),
    providers,
    workloads: workloadCapabilityEntries(env, enabledByWorkloadId),
    provider_budget_policy_state: budgetPolicy.state,
    provider_budgets: providerBudgets,
    paid_execution: "parked",
  };
  const ownerTraining = await getOwnerTrainingCapability(env, owner, budgetPolicy);
  result.machine_state.owner_selected_training = ownerTraining.capability;
  if (!ownerTraining.adapter_configured) {
    result.provider_adapter = { configured: false, available: false, blocker: "PROVIDER_ADAPTER_NOT_CONFIGURED" };
    return result;
  }
  if (!ownerTraining.adapter_available) {
    result.provider_adapter = { configured: true, available: false, blocker: "PROVIDER_ADAPTER_UNAVAILABLE" };
    return result;
  }
  result.provider_adapter = { configured: true, available: true,
    capabilities: ownerTraining.adapter_capabilities };
  const adapterWorkloads = new Map(Object.values(WORKLOADS)
    .filter((workload) => workload.adapter_manifest && PROVIDER_ROUTES[workload.provider]?.adapter_hosted)
    .map((workload) => [workload.provider, workload.id]));
  try {
    for (const [providerId, workloadId] of adapterWorkloads) {
      const adapterProvider = ownerTraining.adapter_providers.find((item) => item?.id === providerId);
      const provider = result.providers.find((item) => item.id === providerId);
      const modalGpuRoute = providerId === PROVIDER_ROUTES.modal_gpu.id;
      const budgetProviderId = PROVIDERS[PROVIDER_ROUTES[providerId].provider].budget_provider;
      const budgetProvider = modalGpuRoute ? modalProviderBudget
        : providerBudgets.find((item) => item.provider === budgetProviderId);
      provider.configured = adapterProvider?.configured === true;
      provider.enabled = providerBudgetPolicyReady && provider.configured && adapterProvider?.paid_fallback === false &&
        (!modalGpuRoute || Number.isSafeInteger(budgetProvider?.monthly_remaining_microusd) &&
          budgetProvider.monthly_remaining_microusd >= 10_000 && env.MODAL_GPU_WORKLOAD_ADMISSION_ENABLED === "true" &&
          budgetProvider?.modal_gpu_admission_enabled === true);
      if (modalGpuRoute && budgetProvider) {
        provider.budget_scope = budgetProvider.scope;
        provider.monthly_limit_usd = budgetProvider.monthly_limit_usd;
        provider.per_run_limit_usd = budgetProvider.per_run_limit_usd;
      }
      provider.blocker = provider.enabled ? null : (!providerBudgetPolicyReady ? "PROVIDER_BUDGET_POLICY_UNAVAILABLE" : modalGpuRoute
        ? (!provider.configured ? "MODAL_GPU_PROVIDER_NOT_CONFIGURED"
          : (budgetProvider?.monthly_remaining_microusd ?? 0) < 10_000 ? "PROVIDER_BUDGET_EXHAUSTED"
            : "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED")
        : "FREE_PROVIDER_NOT_CONFIGURED");
      const workload = result.workloads.find((item) => item.id === workloadId);
      if (workload) workload.enabled = provider.enabled;
    }
  } catch {
    result.provider_adapter = { configured: true, available: false, blocker: "PROVIDER_ADAPTER_UNAVAILABLE" };
    ownerTraining.capability.blocker = "OWNER_TRAINING_ADAPTER_READINESS_UNAVAILABLE";
  }
  return result;
}

