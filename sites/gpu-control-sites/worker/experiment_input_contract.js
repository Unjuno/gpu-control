import { WORKLOADS, WORKLOAD_IDS } from "./workload_registry.js";
import { MAP_TRAINING_MAX_COST_MICROUSD, MAP_TRAINING_MAX_RUNTIME_SECONDS } from "./training_plan.js";
import { MAP_TRAINING_REPOSITORY } from "./training_source.js";
import { RUNPOD_WORKLOAD, validRunpodApprovedPlan, validRunpodPrepare } from "./runpod_plan.js";

const WORKLOAD = WORKLOADS.tiny_stories.id;
const KAGGLE_WORKLOAD = WORKLOADS.kaggle_training.id;
const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_WORKLOAD = WORKLOADS.modal_gpu_canary.id;
const ORBITUNE_REPOSITORY = WORKLOADS.kaggle_training.repository;
const ORBITUNE_SOURCE_SHA = WORKLOADS.kaggle_training.source_sha;
const GPU_CONTROL_REPOSITORY = WORKLOADS.modal_gpu_canary.repository;
const MODAL_GPU_SOURCE_SHA = WORKLOADS.modal_gpu_canary.source_sha;
const MODAL_GPU_IMAGE_DIGEST = WORKLOADS.modal_gpu_canary.adapter_manifest.image_digest;
const MODAL_SANDBOX_COST_CEILING_USD = WORKLOADS.tiny_stories.cost_ceiling_usd;
const MODAL_MAX_RUNTIME_SECONDS = WORKLOADS.tiny_stories.runtime_seconds;
const MODAL_SANDBOX_CPU_LIMIT_CORES = 1;
const MODAL_SANDBOX_MEMORY_LIMIT_MIB = 512;

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  if (typeof value === "number" && !Number.isFinite(value)) throw new Error("INVALID_ARGUMENTS");
  return JSON.stringify(value);
}

function randomHex(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function validPlan(input, env) {
  return input && typeof input === "object" && !Array.isArray(input) &&
    Object.keys(input).sort().join(",") === "commit,idempotency_key,max_cost_usd,parameters,repository,runtime_seconds,workload" &&
    input.workload === WORKLOAD &&
    typeof env.CPU_WORKLOAD_IMAGE_DIGEST === "string" && /^sha256:[0-9a-f]{64}$/.test(env.CPU_WORKLOAD_IMAGE_DIGEST) &&
    typeof input.repository === "string" && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(input.repository) &&
    typeof input.commit === "string" && /^[0-9a-f]{40}$/.test(input.commit) &&
    input.repository === env.CPU_WORKLOAD_REPOSITORY && input.commit === env.CPU_WORKLOAD_SOURCE_SHA &&
    input.max_cost_usd === MODAL_SANDBOX_COST_CEILING_USD && Number.isInteger(input.runtime_seconds) && input.runtime_seconds >= 1 && input.runtime_seconds <= 30 &&
    input.parameters && !Array.isArray(input.parameters) && Object.keys(input.parameters).sort().join(",") === "max_new_tokens,prompt,seed" &&
    typeof input.parameters.prompt === "string" && input.parameters.prompt.length >= 1 &&
    new TextEncoder().encode(input.parameters.prompt).byteLength <= 128 &&
    new TextDecoder().decode(new TextEncoder().encode(input.parameters.prompt)) === input.parameters.prompt &&
    !/[\u0000-\u001f\u007f]/.test(input.parameters.prompt) &&
    Number.isInteger(input.parameters.max_new_tokens) && input.parameters.max_new_tokens >= 1 && input.parameters.max_new_tokens <= 32 &&
    Number.isInteger(input.parameters.seed) && input.parameters.seed >= 1 && input.parameters.seed <= 1000000 &&
    typeof input.idempotency_key === "string" && /^[A-Za-z0-9_.:-]{8,128}$/.test(input.idempotency_key);
}

export function validRegisteredPrepare(input) {
  if (!input || typeof input !== "object" || Array.isArray(input) ||
      !["workload_id", "idempotency_key,workload_id"].includes(Object.keys(input).sort().join(",")) ||
      (input.idempotency_key !== undefined && (typeof input.idempotency_key !== "string" || !/^[A-Za-z0-9_.:-]{8,128}$/.test(input.idempotency_key)))) return false;
  return WORKLOAD_IDS.includes(input.workload_id);
}

export function validRegisteredZeroGpuPrepare(input) {
  return input && typeof input === "object" && !Array.isArray(input) &&
    ["workload_id", "idempotency_key,workload_id", "idempotency_key,source_run_id,workload_id", "source_run_id,workload_id"].includes(Object.keys(input).sort().join(",")) &&
    (input.idempotency_key === undefined || (typeof input.idempotency_key === "string" && /^[A-Za-z0-9_.:-]{8,128}$/.test(input.idempotency_key))) &&
    input.workload_id === ZERO_GPU_WORKLOAD &&
    (input.source_run_id === undefined || (typeof input.source_run_id === "string" && /^[0-9a-f]{32}$/.test(input.source_run_id)));
}



export function safeJson(value) {
  try { return typeof value === "string" ? JSON.parse(value) : null; } catch { return null; }
}

export function validGatewayPrepare(input) {
  if (!input || typeof input !== "object" || Array.isArray(input) ||
      !["commit,idempotency_key,max_cost_usd,parameters,repository,runtime_seconds,workload",
        "commit,idempotency_key,max_cost_usd,parameters,repository,runtime_seconds,source_run_id,workload"].includes(Object.keys(input).sort().join(",")) ||
      typeof input.idempotency_key !== "string" || !/^[A-Za-z0-9_.:-]{8,128}$/.test(input.idempotency_key) ||
      typeof input.max_cost_usd !== "string" ||
      !Number.isSafeInteger(input.runtime_seconds) || !input.parameters ||
      typeof input.parameters !== "object" || Array.isArray(input.parameters)) return false;
  if (input.source_run_id !== undefined && input.workload !== ZERO_GPU_WORKLOAD) return false;
  if (input.workload === MODAL_GPU_WORKLOAD) {
    return input.repository === GPU_CONTROL_REPOSITORY && input.commit === MODAL_GPU_SOURCE_SHA &&
      input.max_cost_usd === WORKLOADS.modal_gpu_canary.cost_ceiling_usd &&
      input.runtime_seconds === WORKLOADS.modal_gpu_canary.runtime_seconds &&
      Object.keys(input.parameters).length === 0;
  }
  if (input.repository !== ORBITUNE_REPOSITORY || input.commit !== ORBITUNE_SOURCE_SHA ||
      !/^0(?:\.0{1,6})?$/.test(input.max_cost_usd)) return false;
  if (input.workload === KAGGLE_WORKLOAD) {
    return input.runtime_seconds >= 1 && input.runtime_seconds <= WORKLOADS.kaggle_training.runtime_seconds &&
      Object.keys(input.parameters).length === 0;
  }
  if (input.workload !== ZERO_GPU_WORKLOAD || input.runtime_seconds < 1 || input.runtime_seconds > WORKLOADS.huggingface_evaluation.runtime_seconds ||
      Object.keys(input.parameters).sort().join(",") !== "artifact_path,artifact_repo_id,artifact_revision,artifact_sha256") return false;
  if (input.source_run_id !== undefined && (typeof input.source_run_id !== "string" || !/^[0-9a-f]{32}$/.test(input.source_run_id))) return false;
  const parameters = input.parameters;
  return parameters.artifact_repo_id === WORKLOADS.huggingface_evaluation.artifact_repository &&
    /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(parameters.artifact_repo_id) &&
    typeof parameters.artifact_revision === "string" && /^[0-9a-f]{40}$/.test(parameters.artifact_revision) &&
    typeof parameters.artifact_path === "string" && /^runs\/[0-9a-f]{32}\/orbitune-output\.zip$/.test(parameters.artifact_path) &&
    typeof parameters.artifact_sha256 === "string" && /^[0-9a-f]{64}$/.test(parameters.artifact_sha256);
}

export function validGatewayApprovedPlan(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      value.schema_version !== 2 || ![KAGGLE_WORKLOAD, ZERO_GPU_WORKLOAD, MODAL_GPU_WORKLOAD].includes(value.workload)) return false;
  if (value.workload === MODAL_GPU_WORKLOAD) {
    if (value.repository !== GPU_CONTROL_REPOSITORY || value.source_sha !== MODAL_GPU_SOURCE_SHA ||
        value.provider !== "modal_gpu" || value.max_cost_usd !== WORKLOADS.modal_gpu_canary.cost_ceiling_usd ||
        value.image_digest !== MODAL_GPU_IMAGE_DIGEST ||
        value.cost_classification !== "PAID_BOUNDED" || value.known_cost_usd !== null ||
        value.paid_fallback_allowed !== false || !value.provider_evidence ||
        typeof value.provider_evidence !== "object" || Array.isArray(value.provider_evidence)) return false;
  } else if (value.repository !== ORBITUNE_REPOSITORY || value.source_sha !== ORBITUNE_SOURCE_SHA ||
      !["kaggle", "huggingface_space"].includes(value.provider)) return false;
  try {
    const encoded = new TextEncoder().encode(canonical(value));
    return encoded.byteLength >= 1 && encoded.byteLength <= 12 * 1024;
  } catch { return false; }
}



export function validProviderApprovedPlan(value) {
  return validGatewayApprovedPlan(value) || validRunpodApprovedPlan(value);
}

export function normalizeTrainingArguments(name, input, env) {
  const args = { ...input };
  const canonicalRepository = typeof args.repository === "string"
    ? args.repository.replace(/^https:\/\/github\.com\//i, "").toLowerCase() : "";
  if (name === "training_register" && args.commit === undefined &&
      canonicalRepository === MAP_TRAINING_REPOSITORY) {
    args.commit = env.MAP_TRAINING_SOURCE_SHA;
  }
  if (["training_preview", "training_prepare"].includes(name)) {
    if (name === "training_prepare" && args.idempotency_key === undefined) args.idempotency_key = `map-${randomHex(16)}`;
  }
  return args;
}

export function validToolArguments(name, args, env) {
  if (["github_connection_start", "github_connection_status", "github_connection_disconnect",
    "github_repositories"].includes(name)) return Object.keys(args).length === 0;
  if (name === "training_checkpoint") return Object.keys(args).sort().join(",") === "max_bytes,offset,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    Number.isSafeInteger(args.offset) && args.offset >= 0 &&
    Number.isSafeInteger(args.max_bytes) && args.max_bytes >= 1 && args.max_bytes <= 24576;
  if (name === "training_artifact") return Object.keys(args).sort().join(",") === "artifact_id,max_bytes,offset,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.artifact_id === "string" && /^[0-9a-f]{64}$/.test(args.artifact_id) &&
    Number.isSafeInteger(args.offset) && args.offset >= 0 &&
    Number.isSafeInteger(args.max_bytes) && args.max_bytes >= 1 && args.max_bytes <= 24576;
  if (name === "training_submit") return Object.keys(args).sort().join(",") === "approved_plan,plan_fingerprint,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.plan_fingerprint === "string" && /^[0-9a-f]{64}$/.test(args.plan_fingerprint) &&
    args.approved_plan && typeof args.approved_plan === "object" && !Array.isArray(args.approved_plan) &&
    Object.keys(args.approved_plan).length <= 32;
  if (name === "training_prepare") {
    const { idempotency_key: key, ...inputs } = args;
    return typeof key === "string" && /^[A-Za-z0-9_-]{16,128}$/.test(key) &&
      validToolArguments("training_preview", inputs, env);
  }
  if (name === "training_preview") {
    const keys = Object.keys(args).sort().join(",");
    const byRegistration = keys === "registration_id" &&
      typeof args.registration_id === "string" && /^[0-9a-f]{32}$/.test(args.registration_id);
    const bySpec = keys === "execution_spec_id,max_cost_microusd,registration_id,runtime_seconds" &&
      typeof args.execution_spec_id === "string" && /^[0-9a-f]{32}$/.test(args.execution_spec_id) &&
      typeof args.registration_id === "string" && /^[0-9a-f]{32}$/.test(args.registration_id);
    const byId = keys === "max_cost_microusd,registration_id,runtime_seconds" &&
      typeof args.registration_id === "string" && /^[0-9a-f]{32}$/.test(args.registration_id);
    const bySource = keys === "commit,max_cost_microusd,repository,runtime_seconds" &&
      typeof args.repository === "string" && args.repository.length <= 159 &&
      typeof args.commit === "string" && args.commit.length === 40;
    if (byRegistration) return true;
    return (byId || bySource || bySpec) &&
      (!bySpec || (args.runtime_seconds === MAP_TRAINING_MAX_RUNTIME_SECONDS &&
        args.max_cost_microusd <= MAP_TRAINING_MAX_COST_MICROUSD)) &&
      Number.isSafeInteger(args.runtime_seconds) &&
      args.runtime_seconds >= 120 && args.runtime_seconds <= 3000 &&
      Number.isSafeInteger(args.max_cost_microusd) && args.max_cost_microusd >= 1 &&
      args.max_cost_microusd <= 1_000_000;
  }
  if (name === "training_list") return Object.keys(args).length === 0;
  if (name === "training_inspect") return Object.keys(args).join(",") === "registration_id" &&
    typeof args.registration_id === "string" && /^[0-9a-f]{32}$/.test(args.registration_id);
  if (name === "training_register") {
    const keys = Object.keys(args);
    const allowed = new Set(["repository", "commit", "dataset", "run_name", "steps"]);
    const canonicalRepository = typeof args.repository === "string"
      ? args.repository.replace(/^https:\/\/github\.com\//i, "").toLowerCase() : "";
    const hasPinnedMapCommit = args.commit === env.MAP_TRAINING_SOURCE_SHA &&
      canonicalRepository === MAP_TRAINING_REPOSITORY;
    return keys.includes("repository") && keys.every(key => allowed.has(key)) &&
      typeof args.repository === "string" && args.repository.length <= 159 &&
      (args.commit === undefined || (typeof args.commit === "string" && /^[0-9a-f]{40}$/.test(args.commit)) || hasPinnedMapCommit) &&
      (args.dataset === undefined || (typeof args.dataset === "string" &&
        /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(args.dataset))) &&
      (args.run_name === undefined || (typeof args.run_name === "string" &&
        /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(args.run_name))) &&
      (args.steps === undefined || (Number.isSafeInteger(args.steps) && args.steps >= 1 && args.steps <= 100000));
  }

  if (name === "experiment_prepare") return validPlan(args, env) || validRunpodPrepare(args, env) ||
    validGatewayPrepare(args) || validRegisteredPrepare(args) || validRegisteredZeroGpuPrepare(args);
  if (name === "experiment_submit" && args.provider_approved_plan !== undefined) return Object.keys(args).sort().join(",") === "plan_fingerprint,provider_approved_plan,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.plan_fingerprint === "string" && /^[0-9a-f]{64}$/.test(args.plan_fingerprint) &&
    validProviderApprovedPlan(args.provider_approved_plan);
  if (name === "experiment_submit") return Object.keys(args).sort().join(",") === "approved_plan,plan_fingerprint,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.plan_fingerprint === "string" && /^[0-9a-f]{64}$/.test(args.plan_fingerprint) &&
    !!args.approved_plan && Object.keys(args.approved_plan).sort().join(",") ===
      "commit,control_function_cost_included,cpu_limit_physical_cores,estimated_sandbox_cost_usd,gpu_allowed,max_cost_usd,max_new_tokens,memory_limit_mib,prompt,repository,runtime_seconds,seed,workload" &&
    args.approved_plan.workload === WORKLOAD &&
    typeof args.approved_plan.repository === "string" && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(args.approved_plan.repository) &&
    typeof args.approved_plan.commit === "string" && /^[0-9a-f]{40}$/.test(args.approved_plan.commit) &&
    typeof args.approved_plan.prompt === "string" && args.approved_plan.prompt.length >= 1 && args.approved_plan.prompt.length <= 128 &&
    Number.isSafeInteger(args.approved_plan.max_new_tokens) && args.approved_plan.max_new_tokens >= 1 && args.approved_plan.max_new_tokens <= 32 &&
    Number.isSafeInteger(args.approved_plan.seed) && args.approved_plan.seed >= 1 && args.approved_plan.seed <= 1000000 &&
    Number.isSafeInteger(args.approved_plan.runtime_seconds) && args.approved_plan.runtime_seconds >= 1 && args.approved_plan.runtime_seconds <= MODAL_MAX_RUNTIME_SECONDS &&
    typeof args.approved_plan.estimated_sandbox_cost_usd === "string" && /^0\.[0-9]{4,6}$/.test(args.approved_plan.estimated_sandbox_cost_usd) &&
    args.approved_plan.max_cost_usd === MODAL_SANDBOX_COST_CEILING_USD &&
    args.approved_plan.cpu_limit_physical_cores === MODAL_SANDBOX_CPU_LIMIT_CORES &&
    args.approved_plan.memory_limit_mib === MODAL_SANDBOX_MEMORY_LIMIT_MIB &&
    args.approved_plan.gpu_allowed === false && args.approved_plan.control_function_cost_included === false;
  if (name === "experiment_provider_health") return Object.keys(args).sort().join(",") === "plan_fingerprint,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.plan_fingerprint === "string" && /^[0-9a-f]{64}$/.test(args.plan_fingerprint);
  if (["experiment_capabilities", "experiment_reconcile"].includes(name)) return Object.keys(args).length === 0;
  if (name === "experiment_list") return Object.keys(args).every((key) =>
      ["workload", "provider", "state", "limit", "cursor"].includes(key)) &&
    (args.workload === undefined || WORKLOAD_IDS.includes(args.workload)) &&
    (args.provider === undefined || ["modal_cpu", "modal_gpu", "runpod_gpu", "kaggle", "huggingface_space", "retired_local_runner", "unknown"].includes(args.provider)) &&
    (args.state === undefined || ["prepared", "queued", "running", "succeeded", "failed", "cancelled", "expired", "uncertain"].includes(args.state)) &&
    (args.limit === undefined || (Number.isSafeInteger(args.limit) && args.limit >= 1 && args.limit <= 50)) &&
    (args.cursor === undefined || (typeof args.cursor === "string" && /^[0-9]{1,12}:[0-9a-f]{32}$/.test(args.cursor)));
  if (["training_status", "training_cancel", "experiment_status", "experiment_result", "experiment_cancel"].includes(name)) return Object.keys(args).join(",") === "run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id);
  if (name === "experiment_artifact") return Object.keys(args).sort().join(",") === "artifact_id,max_bytes,offset,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) && typeof args.artifact_id === "string" &&
    /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(args.artifact_id) && Number.isSafeInteger(args.offset) && args.offset >= 0 &&
    Number.isSafeInteger(args.max_bytes) && args.max_bytes >= 1 && args.max_bytes <= 24576;
  return false;
}

