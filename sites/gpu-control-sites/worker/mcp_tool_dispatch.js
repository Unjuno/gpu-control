import { handleGithubTool, isGithubTool } from "./github_tools.js";
import { handleGoogleColabTool, isGoogleColabTool } from "./google_colab_tools.js";
import { handleTrainingTool, isTrainingTool } from "./training_tools.js";
import { createOwnedRepositoryReadToken } from "./github_app_connection.js";
import { prepareRunpodExperiment, RUNPOD_WORKLOAD } from "./runpod_plan.js";
import { submitRunpodExperiment, synchronizeRunpodExperiment } from "./runpod_lifecycle.js";
import { registeredPrepareArguments, resolveZeroGpuPrepare } from "./registered_prepare.js";
import { WORKLOADS } from "./workload_registry.js";
import { reserveProviderBudget } from "./provider_budget_policy.js";
import { getExperimentCapabilities } from "./provider_capabilities.js";
import { modalConfigured } from "./modal_http_client.js";
import { reserveModalStatusCheck, synchronizeModalRun } from "./modal_cpu_lifecycle.js";
import { maybeDelegateRunTool, prepareDelegatedExperiment, submitDelegatedExperiment } from "./delegated_experiment_lifecycle.js";
import { providerHealthDiagnostic } from "./provider_health_diagnostic.js";
import { prepareModalCpuPlan } from "./prepare_modal_cpu_plan.js";
import { listExperiments } from "./experiment_list.js";
import { readExperimentStatus } from "./experiment_status.js";
import { cancelLocalRun } from "./local_run_cancellation.js";
import { reconcileProviderRuns } from "./run_reconciliation.js";
import { submitModalCpuRun } from "./modal_cpu_submission.js";
import { callProviderAdapterTool, providerAdapterConfigured } from "./provider_adapter_client.js";
import { readRunResultArtifact } from "./run_artifacts.js";
import { validGatewayPrepare, validToolArguments } from "./experiment_input_contract.js";
import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { prepareGoogleColabExperiment } from "./google_colab_plan.js";
import { submitGoogleColabExperiment, googleColabRunTool } from "./google_colab_lifecycle.js";

const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_PROVIDER_USAGE_LIMIT_USD = "30.00";

export async function modalGpuProviderEvidence(env, now) {
  return readModalGpuAccountEvidence(env, { gpu: "T4", usageLimitUsd: MODAL_GPU_PROVIDER_USAGE_LIMIT_USD, now });
}

/**
 * Route one already-authenticated, schema-validated MCP tool call to its domain.
 * HTTP transport and public MCP envelope construction stay in the entrypoint.
 */
export async function dispatchMcpTool(name, args, request, env, context, principal, services) {
  const owner = principal?.owner_id;
  if (!owner) throw new Error(principal?.denied === "forbidden" ? "SITE_USER_NOT_AUTHORIZED" : "AUTHENTICATED_SITE_USER_REQUIRED");
  if (!env.DB) return { schema_version: 2, status: "blocked", human_summary: "D1 database is not configured.", machine_state: {}, next_allowed_actions: [], blocking_reason: "D1_NOT_CONFIGURED" };
  if (isGoogleColabTool(name)) return handleGoogleColabTool(name, env, owner);
  if (isGithubTool(name)) return handleGithubTool(name, env, owner);
  if (isTrainingTool(name)) return handleTrainingTool(name, args, { env, owner,
    delegate: callProviderAdapterTool, isConfigured: providerAdapterConfigured,
    getSourceToken: async (repository) => (await createOwnedRepositoryReadToken(env, env.DB, owner, repository)).token });
  if (name === "experiment_provider_health") return providerHealthDiagnostic(env, owner, args.run_id, args.plan_fingerprint);
  if (name === "experiment_capabilities") return getExperimentCapabilities(env, owner, { modalConfigured });
  if (name === "experiment_prepare") {
    if (args.provider === "google_colab") return prepareGoogleColabExperiment(env, owner, args, {
      getSourceToken: async (repository) => (await createOwnedRepositoryReadToken(env, env.DB, owner, repository)).token,
    });
    let prepareArgs = args;
    if (args.workload_id === ZERO_GPU_WORKLOAD) {
      prepareArgs = await resolveZeroGpuPrepare(env, owner, args);
      if (!prepareArgs) return { schema_version: 2, status: "blocked",
        human_summary: "指定された所有者のKaggle実行から、cleanup済みの固定artifact参照を解決できませんでした。Kaggle run IDを確認してください。",
        machine_state: { workload: ZERO_GPU_WORKLOAD, source_run_id: args.source_run_id },
        next_allowed_actions: ["experiment_list"], blocking_reason: "KAGGLE_ARTIFACT_REFERENCE_UNAVAILABLE" };
    } else if (args.workload_id) {
      prepareArgs = registeredPrepareArguments(args, env);
      if (!prepareArgs) throw new Error("REGISTERED_WORKLOAD_DEFAULTS_UNAVAILABLE");
    }
    if (prepareArgs.workload === RUNPOD_WORKLOAD) {
      return prepareRunpodExperiment(env, owner, prepareArgs);
    }
    if (validGatewayPrepare(prepareArgs)) return prepareDelegatedExperiment(env, owner, prepareArgs, {
      modalGpuProviderEvidence: services.modalGpuProviderEvidence,
    });
    return prepareModalCpuPlan(env, owner, prepareArgs);
  }
  if (name === "experiment_submit") {
    if (!validToolArguments(name, args, env)) throw new Error("INVALID_ARGUMENTS");
    if (args.provider_approved_plan?.provider === "google_colab") {
      return submitGoogleColabExperiment(env, owner, args);
    }
    if (args.provider_approved_plan?.provider === "runpod_gpu") {
      return submitRunpodExperiment(env, owner, args, {
        reserveBudget: (input) => reserveProviderBudget(env, input),
        context,
      });
    }
    if (args.provider_approved_plan !== undefined) return submitDelegatedExperiment(env, owner, args, {
      modalGpuProviderEvidence: services.modalGpuProviderEvidence, randomHex: services.randomHex,
    });
    return submitModalCpuRun(env, owner, args, request, {
      randomHex: services.randomHex, authorizationUrl: services.authorizationUrl,
      submitSummary: services.submitSummary, synchronizeModalRun,
    });
  }
  if (name === "experiment_status" || name === "experiment_result") {
    const delegated = await maybeDelegateRunTool(env, owner, name, args);
    if (delegated) return delegated;
    return readExperimentStatus(env, owner, name, args, {
      synchronizeRunpod: synchronizeRunpodExperiment,
      modalConfigured,
      reserveModalStatusCheck,
      synchronizeModalRun,
    });
  }
  if (name === "experiment_cancel") {
    const delegated = await maybeDelegateRunTool(env, owner, name, args);
    if (delegated) return delegated;
    return cancelLocalRun(env, owner, args.run_id, { synchronizeRunpod: synchronizeRunpodExperiment });
  }
  if (name === "experiment_reconcile") return reconcileProviderRuns(env, owner, {
    maybeDelegateRunTool, synchronizeRunpod: synchronizeRunpodExperiment, googleColabRunTool,
  });
  if (name === "experiment_artifact") {
    const delegated = await maybeDelegateRunTool(env, owner, name, args);
    if (delegated) return delegated;
    return readRunResultArtifact(env, owner, args);
  }
  if (name === "experiment_list") return listExperiments(env, owner, args);
  throw new Error("UNKNOWN_TOOL");
}
