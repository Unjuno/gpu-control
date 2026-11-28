import { canonicalJson } from "./canonical_json.js";
import { WORKLOADS } from "./workload_registry.js";

const DELEGATED_WORKLOADS = [WORKLOADS.kaggle_training.id,
  WORKLOADS.huggingface_evaluation.id, WORKLOADS.modal_gpu_canary.id];

export async function readDelegatedPlan(env, owner, runId) {
  try {
    const row = await env.DB.prepare(`SELECT id, fingerprint, workload, approved_plan_json, state, created_at, expires_at,
        provider_handle_json, provider_state, provider_response_json, updated_at, cancelled_at, terminal_at,
        source_run_id, submit_attempted_at
      FROM gateway_delegated_plans WHERE owner_id=? AND id=?`).bind(owner, runId).first();
    return row && DELEGATED_WORKLOADS.includes(row.workload) &&
      typeof row.approved_plan_json === "string" ? row : null;
  } catch {
    return null;
  }
}

function boundedProviderHandle(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const encoded = canonicalJson(value);
  return new TextEncoder().encode(encoded).byteLength <= 16 * 1024 ? encoded : null;
}

export async function persistProviderAdapterObservation(env, owner, runId, response) {
  const machine = response?.machine_state;
  if (!machine || typeof machine !== "object" || Array.isArray(machine)) return;
  const handleJson = machine.provider_handle === undefined ? null : boundedProviderHandle(machine.provider_handle);
  if (machine.provider_handle !== undefined && handleJson === null) {
    throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
  }
  const state = typeof machine.state === "string" && /^[a-z_]{1,32}$/.test(machine.state)
    ? machine.state : null;
  const responseJson = canonicalJson(response);
  if (new TextEncoder().encode(responseJson).byteLength > 64 * 1024) {
    throw new Error("GATEWAY_DELEGATION_RESPONSE_TOO_LARGE");
  }
  const now = Math.floor(Date.now() / 1000);
  await env.DB.prepare(`UPDATE gateway_delegated_plans
    SET provider_handle_json=COALESCE(?, provider_handle_json), provider_state=COALESCE(?, provider_state),
      provider_response_json=?, updated_at=? WHERE owner_id=? AND id=?`)
    .bind(handleJson, state, responseJson, now, owner, runId).run();
}

export function publicProviderAdapterResponse(response) {
  if (!response?.machine_state || typeof response.machine_state !== "object" ||
      Array.isArray(response.machine_state) || response.machine_state.provider_handle === undefined) {
    return response;
  }
  const { provider_handle: _privateHandle, ...publicMachineState } = response.machine_state;
  return { ...response, machine_state: publicMachineState };
}
