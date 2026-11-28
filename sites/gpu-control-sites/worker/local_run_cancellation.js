export async function cancelLocalRun(env, owner, runId, { synchronizeRunpod }) {
  const selectRun = () => env.DB.prepare("SELECT id, state, cancel_requested, cleanup_state FROM runs WHERE id = ? AND owner_id = ?")
    .bind(runId, owner).first();
  let row = await selectRun();
  if (!row) throw new Error("RUN_NOT_FOUND");
  let cancelProvider = null;
  try {
    cancelProvider = await env.DB.prepare(`SELECT p.provider FROM plans p JOIN runs r ON r.plan_id=p.id
      WHERE r.id=? AND r.owner_id=?`).bind(runId, owner).first();
  } catch {}
  if (cancelProvider?.provider === "runpod_gpu") {
    if (row.state === "running" && row.cancel_requested !== 1) {
      const requested = await env.DB.prepare(`UPDATE runs SET cancel_requested=1, updated_at=?
        WHERE id=? AND owner_id=? AND state='running' AND cancel_requested=0 RETURNING id, state, cancel_requested`)
        .bind(Math.floor(Date.now() / 1000), runId, owner).first();
      if (requested) row = requested;
      else row = await selectRun();
      if (!row) throw new Error("RUN_NOT_FOUND");
    }
    const runpod = await synchronizeRunpod(env, owner, runId, { cancel: true });
    if (!runpod) throw new Error("RUN_NOT_FOUND");
    const cleanupConfirmed = ["succeeded", "failed", "cancelled"].includes(runpod.state) && runpod.cleanup_state === "confirmed";
    return { schema_version: 2, status: cleanupConfirmed ? "ok" : "pending",
      human_summary: cleanupConfirmed
        ? "Runpod reached a terminal state and cleanup was confirmed."
        : "Runpod cancellation is not yet confirmed. The same run remains active or uncertain; check its status for provider receipt recovery and cleanup.",
      machine_state: { run_id: runpod?.id || runId, state: runpod?.provider_phase === "uncertain" ? "uncertain" : runpod?.state,
        provider_phase: runpod?.provider_phase || "uncertain",
        cancellation_requested: runpod?.cancel_requested === 1 || runpod?.state === "cancelled",
        provider_resource_created: runpod?.provider_job_id ? true : "unknown",
        cleanup_state: runpod?.cleanup_state || "unknown" },
      next_allowed_actions: ["experiment_status"], blocking_reason: null };
  }
  const now = Math.floor(Date.now() / 1000);
  if (row.state === "queued") {
    const cancelled = await env.DB.prepare(`UPDATE runs SET state='cancelled', failure_code='caller_cancelled_before_start',
        cleanup_state='confirmed', updated_at=? WHERE id=? AND owner_id=? AND state='queued' RETURNING id, state, cleanup_state`)
      .bind(now, runId, owner).first();
    if (cancelled) return { schema_version: 2, status: "ok", human_summary: "Queued experiment cancelled before Runner start.",
      machine_state: { run_id: cancelled.id, state: cancelled.state, cleanup_state: cancelled.cleanup_state, cancellation_requested: false },
      next_allowed_actions: ["experiment_status"], blocking_reason: null };
    row = await selectRun();
    if (!row) throw new Error("RUN_NOT_FOUND");
  }
  if (row.state === "running" && row.cancel_requested !== 1) {
    const requested = await env.DB.prepare(`UPDATE runs SET cancel_requested=1, updated_at=?
        WHERE id=? AND owner_id=? AND state='running' AND cancel_requested=0 RETURNING id, state, cancel_requested`)
      .bind(now, runId, owner).first();
    if (requested) row = requested;
    else row = await selectRun();
    if (!row) throw new Error("RUN_NOT_FOUND");
  }
  if (row.state === "running" && row.cancel_requested === 1) {
    return { schema_version: 2, status: "pending", human_summary: "Cancellation requested; Modal will stop and clean up the workload.",
      machine_state: { run_id: row.id, state: row.state, cancellation_requested: true, cleanup_state: row.cleanup_state },
      next_allowed_actions: ["experiment_status"], blocking_reason: null };
  }
  return { schema_version: 2, status: "ok", human_summary: "Run is already terminal; no cancellation was needed.",
    machine_state: { run_id: row.id, state: row.state, cancellation_requested: false, cleanup_state: row.cleanup_state },
    next_allowed_actions: ["experiment_status"], blocking_reason: null };
}
