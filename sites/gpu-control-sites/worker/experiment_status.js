import { executionOrigin } from "./experiment_list.js";

const RUN_STATUS_QUERY = `SELECT r.id, r.state, r.created_at, r.updated_at, r.result_json,
    r.failure_code, r.cleanup_state, r.cleanup_receipt_json, r.cancel_requested,
    r.result_artifact_id, r.result_artifact_sha256, r.result_artifact_size, r.lease_id,
    p.workload, p.repository, p.source_sha, p.image_digest, p.parameters_json,
    p.fingerprint, p.runtime_seconds, p.idempotency_key, p.provider
  FROM runs r JOIN plans p ON p.id = r.plan_id WHERE r.id = ? AND r.owner_id = ?`;

async function loadRun(env, owner, runId) {
  return env.DB.prepare(RUN_STATUS_QUERY).bind(runId, owner).first();
}

export async function readExperimentStatus(env, owner, name, args, providers) {
  let row = await loadRun(env, owner, args.run_id);
  if (!row) throw new Error("RUN_NOT_FOUND");
  if (row.provider === "runpod_gpu") {
    await providers.synchronizeRunpod(env, owner, args.run_id);
    row = await loadRun(env, owner, args.run_id);
  }
  let providerSyncSkipped = null;
  if (["queued", "running"].includes(row.state) && row.provider === "modal_cpu" && providers.modalConfigured(env)) {
    let reserved = false;
    try {
      reserved = await providers.reserveModalStatusCheck(env, Math.floor(Date.now() / 1000));
    } catch {
      providerSyncSkipped = "MODAL_STATUS_CHECK_BUDGET_UNAVAILABLE";
    }
    if (!providerSyncSkipped && !reserved) providerSyncSkipped = "MODAL_STATUS_CHECK_RATE_LIMITED";
    if (reserved) await providers.synchronizeModalRun(env, row.id, owner, { cancel: row.cancel_requested === 1 });
    row = await loadRun(env, owner, args.run_id);
  }
  if (name === "experiment_result" && row.state !== "succeeded") return {
    schema_version: 2, status: "blocked", human_summary: "Result is not ready.",
    machine_state: { run_id: row.id, state: row.state }, next_allowed_actions: ["experiment_status"],
    blocking_reason: "RESULT_NOT_READY",
  };
  const result = row.result_json ? JSON.parse(row.result_json) : null;
  if (result && typeof result.logs === "string") {
    result.logs_truncated = result.logs.length > 4096;
    result.logs = result.logs.slice(-4096);
  }
  const machine = { run_id: row.id, state: row.state, created_at: row.created_at, updated_at: row.updated_at,
    workload: row.workload, repository: row.repository, source_sha: row.source_sha,
    execution_origin: executionOrigin(row), image_digest: row.image_digest,
    parameters: JSON.parse(row.parameters_json), result, failure_code: row.failure_code,
    cleanup_state: row.cleanup_state, cancellation_requested: row.cancel_requested === 1,
    ...(providerSyncSkipped ? { provider_sync_skipped: providerSyncSkipped } : {}),
    result_artifact: row.result_artifact_id ? { artifact_id: row.result_artifact_id,
      sha256: row.result_artifact_sha256, size_bytes: row.result_artifact_size } : null };
  const active = ["queued", "running"].includes(row.state);
  const nextAllowed = active
    ? (row.cancel_requested === 1 ? ["experiment_status"] : ["experiment_status", "experiment_cancel"])
    : (row.state === "succeeded" ? [] : ["experiment_status"]);
  const humanSummary = providerSyncSkipped
    ? `Stored run state retrieved; Modal synchronization skipped (${providerSyncSkipped}).`
    : (name === "experiment_status" ? "Run status retrieved." : "Run result retrieved.");
  return { schema_version: 2, status: "ok", human_summary: humanSummary, machine_state: machine,
    next_allowed_actions: nextAllowed, blocking_reason: null };
}
