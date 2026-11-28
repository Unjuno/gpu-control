import { MAP_TRAINING_MAX_COST_MICROUSD, MAP_TRAINING_MAX_RUNTIME_SECONDS } from "./training_policy.js";
import { MAP_TRAINING_REPOSITORY } from "./training_source.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { MAX_EXPERIMENT_ARTIFACT_CHUNK_BYTES } from "./artifact_transfer_policy.js";

function randomHex(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Apply defaults that belong to a named training operation before validation. */
export function normalizeTrainingArguments(name, input, env) {
  const args = { ...input };
  const canonicalRepository = typeof args.repository === "string"
    ? args.repository.replace(/^https:\/\/github\.com\//i, "").toLowerCase() : "";
  if (name === "training_register" && args.commit === undefined &&
      canonicalRepository === MAP_TRAINING_REPOSITORY) {
    args.commit = mapTrainingConfiguration(env).source_sha;
  }
  if (name === "training_prepare" && args.idempotency_key === undefined) {
    args.idempotency_key = `map-${randomHex(16)}`;
  }
  return args;
}

/** Validate only the owner-scoped training MCP tools. */
export function validTrainingToolArguments(name, args, env) {
  if (name === "training_checkpoint") return Object.keys(args).sort().join(",") === "max_bytes,offset,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    Number.isSafeInteger(args.offset) && args.offset >= 0 &&
    Number.isSafeInteger(args.max_bytes) && args.max_bytes >= 1 &&
    args.max_bytes <= MAX_EXPERIMENT_ARTIFACT_CHUNK_BYTES;
  if (name === "training_artifact") return Object.keys(args).sort().join(",") === "artifact_id,max_bytes,offset,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.artifact_id === "string" && /^[0-9a-f]{64}$/.test(args.artifact_id) &&
    Number.isSafeInteger(args.offset) && args.offset >= 0 &&
    Number.isSafeInteger(args.max_bytes) && args.max_bytes >= 1 &&
    args.max_bytes <= MAX_EXPERIMENT_ARTIFACT_CHUNK_BYTES;
  if (name === "training_submit") return Object.keys(args).sort().join(",") === "approved_plan,plan_fingerprint,run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id) &&
    typeof args.plan_fingerprint === "string" && /^[0-9a-f]{64}$/.test(args.plan_fingerprint) &&
    args.approved_plan && typeof args.approved_plan === "object" && !Array.isArray(args.approved_plan) &&
    Object.keys(args.approved_plan).length <= 32;
  if (name === "training_prepare") {
    const { idempotency_key: key, ...inputs } = args;
    return typeof key === "string" && /^[A-Za-z0-9_-]{16,128}$/.test(key) &&
      validTrainingToolArguments("training_preview", inputs, env);
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
    const mapConfig = mapTrainingConfiguration(env);
    const keys = Object.keys(args);
    const allowed = new Set(["repository", "commit", "dataset", "run_name", "steps"]);
    const canonicalRepository = typeof args.repository === "string"
      ? args.repository.replace(/^https:\/\/github\.com\//i, "").toLowerCase() : "";
    const hasPinnedMapCommit = args.commit === mapConfig.source_sha &&
      canonicalRepository === MAP_TRAINING_REPOSITORY;
    return keys.includes("repository") && keys.every((key) => allowed.has(key)) &&
      typeof args.repository === "string" && args.repository.length <= 159 &&
      (args.commit === undefined || (typeof args.commit === "string" && /^[0-9a-f]{40}$/.test(args.commit)) || hasPinnedMapCommit) &&
      (args.dataset === undefined || (typeof args.dataset === "string" &&
        /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(args.dataset))) &&
      (args.run_name === undefined || (typeof args.run_name === "string" &&
        /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(args.run_name))) &&
      (args.steps === undefined || (Number.isSafeInteger(args.steps) && args.steps >= 1 && args.steps <= 100000));
  }
  if (["training_status", "training_cancel"].includes(name)) return Object.keys(args).join(",") === "run_id" &&
    typeof args.run_id === "string" && /^[0-9a-f]{32}$/.test(args.run_id);
  return false;
}
