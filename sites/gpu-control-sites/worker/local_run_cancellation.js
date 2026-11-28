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
    const runpod = await synchronizeRunpod(env, owner, runId, { cancel: true });
    return { schema_version: 2, status: "ok", human_summary: "Runpod cancellation and cleanup completed.",
      machine_state: { run_id: runpod.id, state: runpod.state, cleanup_state: runpod.cleanup_state },
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
