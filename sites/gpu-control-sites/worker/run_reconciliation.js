import { WORKLOADS } from "./workload_registry.js";
import { GOOGLE_COLAB_WORKLOAD } from "./google_colab_plan.js";

const DELEGATED_WORKLOADS = [WORKLOADS.kaggle_training.id,
  WORKLOADS.huggingface_evaluation.id, WORKLOADS.modal_gpu_canary.id];

async function reconcileDelegatedRun(env, owner, maybeDelegateRunTool) {
  const delegatedRow = await env.DB.prepare(`SELECT id, owner_id FROM gateway_delegated_plans
    WHERE owner_id=? AND state='submitted' AND workload IN (?, ?, ?)
      AND COALESCE(provider_state, 'queued') IN ('queued','running')
    ORDER BY COALESCE(updated_at, created_at), created_at LIMIT 1`)
    .bind(owner, ...DELEGATED_WORKLOADS).first();
  if (!delegatedRow) return null;
  try {
    const result = await maybeDelegateRunTool(env, owner, "experiment_status", { run_id: delegatedRow.id });
    if (!result) throw new Error("RUN_NOT_FOUND");
    return result;
  } catch {
    try {
      await env.DB.prepare(`UPDATE gateway_delegated_plans SET updated_at=?
        WHERE owner_id=? AND id=? AND state='submitted'`)
        .bind(Math.floor(Date.now() / 1000), owner, delegatedRow.id).run();
    } catch {}
    return { schema_version: 2, status: "error",
      human_summary: "Delegated-provider reconciliation failed safely; no new work was submitted.",
      machine_state: { run_id: delegatedRow.id, state: "reconciliation_error" },
      next_allowed_actions: ["experiment_status"], blocking_reason: "DELEGATED_RECONCILIATION_FAILED" };
  }
}

async function reconcileRunpodRun(env, owner, synchronizeRunpod) {
  const row = await env.DB.prepare(`SELECT r.id, r.owner_id FROM runs r JOIN plans p ON p.id=r.plan_id
    LEFT JOIN provider_account_leases l ON l.provider='runpod' AND l.run_id=r.id
    WHERE r.owner_id=? AND p.provider='runpod_gpu' AND (
      r.state IN ('queued','running') OR
      (r.state IN ('succeeded','failed','cancelled') AND r.cleanup_state='confirmed'
        AND l.state IN ('active','cleanup_pending'))
    ) ORDER BY CASE WHEN r.state IN ('succeeded','failed','cancelled') THEN 0 ELSE 1 END, r.created_at LIMIT 1`)
    .bind(owner).first();
  if (!row) return null;
  try {
    const updated = await synchronizeRunpod(env, owner, row.id);
    return { schema_version: 2, status: ["queued", "running"].includes(updated.state) ? "pending" : "ok",
      human_summary: "Runpod Serverless job reconciliation completed.",
      machine_state: { run_id: updated.id, state: updated.state, cleanup_state: updated.cleanup_state },
      next_allowed_actions: ["experiment_status"], blocking_reason: null };
  } catch {
    return { schema_version: 2, status: "error",
      human_summary: "Runpod reconciliation failed safely; no new work was submitted.",
      machine_state: { run_id: row.id, state: "reconciliation_error" },
      next_allowed_actions: ["experiment_status"], blocking_reason: "RUNPOD_RECONCILIATION_FAILED" };
  }
}

async function reconcileGoogleColabRun(env, owner, googleColabRunTool) {
  const row = await env.DB.prepare(`SELECT id FROM gateway_delegated_plans
    WHERE owner_id=? AND workload=? AND state='submitted' AND COALESCE(provider_state, 'queued') IN ('queued','running')
    ORDER BY COALESCE(updated_at, created_at), created_at LIMIT 1`).bind(owner, GOOGLE_COLAB_WORKLOAD).first();
  if (!row) return null;
  try {
    const response = await googleColabRunTool(env, owner, "experiment_status", row.id);
    if (!response) throw new Error("COLAB_RUN_NOT_FOUND");
    return response;
  } catch {
    try { await env.DB.prepare(`UPDATE gateway_delegated_plans SET updated_at=?
      WHERE owner_id=? AND id=? AND state='submitted'`).bind(Math.floor(Date.now() / 1000), owner, row.id).run(); } catch {}
    return { schema_version: 2, status: "error",
      human_summary: "Colab reconciliation failed safely; no new run was created.",
      machine_state: { run_id: row.id, provider: "google_colab", state: "reconciliation_error" },
      next_allowed_actions: ["experiment_status"], blocking_reason: "COLAB_RECONCILIATION_FAILED" };
  }
}

export async function reconcileProviderRuns(env, owner, providers) {
  const colab = await reconcileGoogleColabRun(env, owner, providers.googleColabRunTool);
  const delegated = await reconcileDelegatedRun(env, owner, providers.maybeDelegateRunTool);
  const runpod = await reconcileRunpodRun(env, owner, providers.synchronizeRunpod);
  const active = [colab, delegated, runpod].filter(Boolean);
  if (!active.length) return { schema_version: 2, status: "ok", human_summary: "No active provider run requires reconciliation.",
    machine_state: { active_run: false }, next_allowed_actions: [], blocking_reason: null };
  if (active.length === 1) return { ...active[0],
    human_summary: `Scheduled provider reconciliation completed. ${active[0].human_summary || ""}`.trim() };
  const statuses = active.map((item) => item.status);
  const status = statuses.includes("error") ? "error" : statuses.includes("blocked") ? "blocked"
    : statuses.includes("pending") ? "pending" : "ok";
  return { schema_version: 2, status,
    human_summary: "Scheduled Colab, delegated-provider, and Runpod reconciliation completed.",
    machine_state: { ...(colab ? { google_colab: colab.machine_state } : {}),
      ...(delegated ? { delegated: delegated.machine_state } : {}), ...(runpod ? { runpod: runpod.machine_state } : {}) },
    next_allowed_actions: ["experiment_status"],
    blocking_reason: colab?.blocking_reason || delegated?.blocking_reason || runpod?.blocking_reason || null };
}
