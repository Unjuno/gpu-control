import { readPublicTrainingContract } from "./training_contract.js";
import { ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { sha256Hex } from "./sha256.js";

/** Build the reviewed owner-selected Python plan for the Modal adapter. */
export async function previewModalOwnerTrainingPlan(env, args, source, getSourceToken) {
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
