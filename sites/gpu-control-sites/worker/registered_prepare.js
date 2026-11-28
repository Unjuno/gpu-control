import { safeJson, validRegisteredPrepare, validRegisteredZeroGpuPrepare } from "./experiment_input_contract.js";
import { RUNPOD_WORKLOAD, RUNPOD_REPOSITORY, RUNPOD_RUNTIME_SECONDS } from "./runpod_plan.js";
import { WORKLOADS } from "./workload_registry.js";

const WORKLOAD = WORKLOADS.tiny_stories.id;
const KAGGLE_WORKLOAD = WORKLOADS.kaggle_training.id;
const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_WORKLOAD = WORKLOADS.modal_gpu_canary.id;
const ORBITUNE_REPOSITORY = WORKLOADS.kaggle_training.repository;
const ORBITUNE_SOURCE_SHA = WORKLOADS.kaggle_training.source_sha;
const GPU_CONTROL_REPOSITORY = WORKLOADS.modal_gpu_canary.repository;
const MODAL_GPU_SOURCE_SHA = WORKLOADS.modal_gpu_canary.source_sha;
const RUNPOD_PER_RUN_BUDGET_USD = WORKLOADS.runpod_canary.cost_ceiling_usd;

function randomHex(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function resolveZeroGpuPrepare(env, owner, input) {
  if (!validRegisteredZeroGpuPrepare(input)) return null;
  let sources = [];
  if (input.source_run_id) {
    const local = await env.DB.prepare(`SELECT p.source_sha, r.result_json, r.id AS source_run_id,
        COALESCE(r.completed_at, r.updated_at, r.created_at) AS terminal_at
      FROM runs r JOIN plans p ON p.id=r.plan_id
      WHERE r.id=? AND r.owner_id=? AND r.state='succeeded' AND r.cleanup_state='confirmed'
        AND p.workload=?`).bind(input.source_run_id, owner, KAGGLE_WORKLOAD).first();
    if (local) sources.push({ source_sha: local.source_sha, source_run_id: local.source_run_id, terminal_at: local.terminal_at,
      response: local.result_json, cleanup_confirmed: true });
    const delegated = await env.DB.prepare(`SELECT id AS source_run_id, COALESCE(terminal_at, updated_at, created_at) AS terminal_at,
        approved_plan_json, provider_response_json
      FROM gateway_delegated_plans WHERE owner_id=? AND id=? AND workload=? AND provider_state='succeeded'
        AND state='submitted'`).bind(owner, input.source_run_id, KAGGLE_WORKLOAD).first();
    if (delegated) sources.push({ source_run_id: delegated.source_run_id, terminal_at: delegated.terminal_at,
      source_sha: safeJson(delegated.approved_plan_json)?.source_sha, response: delegated.provider_response_json });
  } else {
    const delegated = await env.DB.prepare(`SELECT id AS source_run_id, COALESCE(terminal_at, updated_at, created_at) AS terminal_at,
        approved_plan_json, provider_response_json
      FROM gateway_delegated_plans WHERE owner_id=? AND workload=? AND provider_state='succeeded' AND state='submitted'
      ORDER BY COALESCE(terminal_at, updated_at, created_at) DESC, id DESC LIMIT 50`).bind(owner, KAGGLE_WORKLOAD).all();
    for (const row of delegated.results || []) sources.push({ source_run_id: row.source_run_id, terminal_at: row.terminal_at,
      source_sha: safeJson(row.approved_plan_json)?.source_sha, response: row.provider_response_json });
    const local = await env.DB.prepare(`SELECT p.source_sha, r.result_json, r.id AS source_run_id,
        COALESCE(r.completed_at, r.updated_at, r.created_at) AS terminal_at FROM runs r
      JOIN plans p ON p.id=r.plan_id WHERE r.owner_id=? AND r.state='succeeded' AND r.cleanup_state='confirmed'
        AND p.workload=? ORDER BY COALESCE(r.completed_at, r.updated_at, r.created_at) DESC, r.id DESC LIMIT 50`).bind(owner, KAGGLE_WORKLOAD).all();
    for (const row of local.results || []) sources.push({ source_sha: row.source_sha, terminal_at: row.terminal_at,
      source_run_id: row.source_run_id, response: row.result_json, cleanup_confirmed: true });
  }
  sources.sort((a, b) => (b.terminal_at || 0) - (a.terminal_at || 0) || b.source_run_id.localeCompare(a.source_run_id));
  let selected = null;
  for (const source of sources) {
    let response;
    try { response = JSON.parse(source.response); } catch { continue; }
    const result = response?.result || response?.machine_state?.result || response;
    if (!source.cleanup_confirmed && response?.machine_state?.cleanup_state !== "confirmed" && !response?.cleanup_confirmed) continue;
    const reference = (Array.isArray(result?.external_artifacts) ? result.external_artifacts : [])
      .find((item) => item?.service === "huggingface_hub" && item?.private === true &&
        item?.repo_type === "model" && item?.run_id === source.source_run_id &&
        item?.source_sha === source.source_sha &&
        item?.path_in_repo === `runs/${source.source_run_id}/orbitune-output.zip` &&
        typeof item?.repo_id === "string" && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(item.repo_id) &&
        typeof item?.revision === "string" && /^[0-9a-f]{40}$/.test(item.revision) &&
        typeof item?.sha256 === "string" && /^[0-9a-f]{64}$/.test(item.sha256));
    if (reference) { selected = { source_run_id: source.source_run_id, reference }; break; }
  }
  if (!selected) return null;
  const { reference } = selected;
  return { repository: ORBITUNE_REPOSITORY, commit: ORBITUNE_SOURCE_SHA,
    workload: ZERO_GPU_WORKLOAD,
    parameters: { artifact_repo_id: reference.repo_id, artifact_revision: reference.revision,
      artifact_path: reference.path_in_repo, artifact_sha256: reference.sha256 },
    runtime_seconds: 60, max_cost_usd: "0", source_run_id: selected.source_run_id,
    idempotency_key: input.idempotency_key || `registered-${randomHex(16)}` };
}

export function registeredPrepareArguments(input, env) {
  if (!validRegisteredPrepare(input)) return null;
  const idempotencyKey = input.idempotency_key || `registered-${randomHex(16)}`;
  const defaults = {
    repository: ORBITUNE_REPOSITORY,
    commit: ORBITUNE_SOURCE_SHA,
    workload: input.workload_id,
    parameters: {},
    runtime_seconds: input.workload_id === KAGGLE_WORKLOAD
      ? WORKLOADS.kaggle_training.runtime_seconds : WORKLOADS.huggingface_evaluation.runtime_seconds,
    max_cost_usd: "0",
    idempotency_key: idempotencyKey,
  };
  if (input.workload_id === WORKLOAD) {
    const definition = WORKLOADS.tiny_stories;
    const sourceSha = env[definition.source_sha_env];
    if (typeof env.CPU_WORKLOAD_REPOSITORY !== "string" ||
        typeof sourceSha !== "string" || !/^[0-9a-f]{40}$/.test(sourceSha)) return null;
    return { repository: env.CPU_WORKLOAD_REPOSITORY, commit: sourceSha,
      workload: WORKLOAD, parameters: { prompt: "Once", max_new_tokens: 1, seed: 61112 },
      runtime_seconds: definition.runtime_seconds, max_cost_usd: definition.cost_ceiling_usd,
      idempotency_key: idempotencyKey };
  }
  if (input.workload_id === RUNPOD_WORKLOAD) {
    const sourceSha = env[WORKLOADS.runpod_canary.source_sha_env];
    if (typeof sourceSha !== "string" || !/^[0-9a-f]{40}$/.test(sourceSha)) return null;
    return { repository: RUNPOD_REPOSITORY, commit: sourceSha,
      workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: RUNPOD_RUNTIME_SECONDS,
      max_cost_usd: RUNPOD_PER_RUN_BUDGET_USD, idempotency_key: idempotencyKey };
  }
  if (input.workload_id === MODAL_GPU_WORKLOAD) {
    return { ...defaults, repository: GPU_CONTROL_REPOSITORY, commit: MODAL_GPU_SOURCE_SHA,
      workload: MODAL_GPU_WORKLOAD, runtime_seconds: WORKLOADS.modal_gpu_canary.runtime_seconds,
      max_cost_usd: WORKLOADS.modal_gpu_canary.cost_ceiling_usd };
  }
  if (input.workload_id === ZERO_GPU_WORKLOAD) return null;
  return defaults;
}

