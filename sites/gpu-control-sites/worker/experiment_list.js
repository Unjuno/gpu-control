import { safeJson, validGatewayApprovedPlan } from "./experiment_input_contract.js";
import { providerAdapterConfigured } from "./provider_adapter_client.js";
import { executionOrigin } from "./execution_origin.js";

export async function listExperiments(env, owner, args) {
  const limit = args.limit || 20;
  const cursor = args.cursor ? args.cursor.split(":") : null;
  const cursorAt = cursor ? Number(cursor[0]) : null;
  const cursorId = cursor?.[1] || null;
  const localBindings = [owner];
  let localWhere = "r.owner_id = ?";
  if (cursor) { localWhere += " AND (r.created_at < ? OR (r.created_at = ? AND r.id < ?))"; localBindings.push(cursorAt, cursorAt, cursorId); }
  if (args.workload) { localWhere += " AND p.workload = ?"; localBindings.push(args.workload); }
  if (args.provider && !["retired_local_runner", "unknown"].includes(args.provider)) {
    localWhere += " AND p.provider = ?"; localBindings.push(args.provider);
  }
  if (args.state) { localWhere += " AND r.state = ?"; localBindings.push(args.state); }
  const { results: localRows } = await env.DB.prepare(`SELECT r.id AS run_id, r.state, r.created_at, r.updated_at,
      r.completed_at, r.cleanup_state, r.result_json, r.result_artifact_id,
      r.lease_id, r.cleanup_receipt_json, p.workload, p.repository, p.source_sha, p.image_digest, p.provider
    FROM runs r JOIN plans p ON p.id = r.plan_id WHERE ${localWhere}
    ORDER BY r.created_at DESC, r.id DESC LIMIT ?`).bind(...localBindings, limit + 1).all();
  const localExperiments = localRows.map((row) => ({ run_id: row.run_id, state: row.state,
    created_at: row.created_at, updated_at: row.updated_at, finished_at: row.completed_at,
    workload: row.workload, repository: row.repository, source_sha: row.source_sha,
    provider: row.provider || executionOrigin({ ...row, id: row.run_id }),
    execution_origin: executionOrigin({ ...row, id: row.run_id }),
    result_available: Boolean(row.result_json || row.result_artifact_id),
    cleanup_state: row.cleanup_state || "unknown" }));
  const delegatedBindings = [owner];
  let delegatedWhere = "owner_id = ?";
  if (cursor) { delegatedWhere += " AND (created_at < ? OR (created_at = ? AND id < ?))"; delegatedBindings.push(cursorAt, cursorAt, cursorId); }
  if (args.workload) { delegatedWhere += " AND workload = ?"; delegatedBindings.push(args.workload); }
  if (args.provider) { delegatedWhere += " AND json_extract(approved_plan_json, '$.provider') = ?"; delegatedBindings.push(args.provider); }
  if (args.state) {
    delegatedWhere += ` AND CASE WHEN cancelled_at IS NOT NULL AND state='prepared' THEN 'cancelled'
      WHEN state='prepared' AND expires_at < ? THEN 'expired' WHEN state='prepared' THEN 'prepared'
      WHEN submit_attempted_at IS NOT NULL AND provider_state IS NULL THEN 'uncertain'
      ELSE COALESCE(provider_state, 'queued') END = ?`;
    delegatedBindings.push(Math.floor(Date.now() / 1000), args.state);
  }
  let delegatedExperiments = [];
  try {
    const { results: delegatedRows } = await env.DB.prepare(`SELECT id AS run_id, state AS plan_state,
        cancelled_at, submit_attempted_at, provider_state, provider_response_json, terminal_at,
        created_at, COALESCE(updated_at, created_at) AS updated_at,
        workload, source_run_id, approved_plan_json, expires_at
      FROM gateway_delegated_plans WHERE ${delegatedWhere}
      ORDER BY created_at DESC, id DESC LIMIT ?`).bind(...delegatedBindings, limit + 1).all();
    delegatedExperiments = delegatedRows.flatMap((row) => {
      const plan = safeJson(row.approved_plan_json);
      if (!validGatewayApprovedPlan(plan)) return [];
      const response = safeJson(row.provider_response_json);
      const result = response?.result || response?.machine_state?.result || null;
      const state = row.cancelled_at && row.plan_state === "prepared" ? "cancelled"
        : row.plan_state === "prepared" ? (row.expires_at < Math.floor(Date.now() / 1000) ? "expired" : "prepared")
          : row.submit_attempted_at && !row.provider_state ? "uncertain" : (row.provider_state || "queued");
      const cleanup = response?.machine_state?.cleanup_state || result?.cleanup_state ||
        (response?.cleanup_confirmed === true || (state === "cancelled" && !row.submit_attempted_at)
          ? "confirmed" : "unknown");
      const finishedAt = row.terminal_at || (state === "cancelled" ? row.cancelled_at : null) ||
        (["succeeded", "failed", "expired"].includes(state) ? row.updated_at : null);
      return [{ run_id: row.run_id, state, created_at: row.created_at, updated_at: row.updated_at,
        finished_at: finishedAt, workload: row.workload, repository: plan.repository,
        source_sha: plan.source_sha, image_digest: plan.image_digest, provider: plan.provider,
        execution_origin: plan.provider, result_available: Boolean(result), cleanup_state: cleanup,
        ...(row.source_run_id ? { source_run_id: row.source_run_id } : {}) }];
    });
  } catch (error) {
    if (!String(error?.message || "").includes("no such column")) throw error;
  }
  const byRun = new Map();
  for (const experiment of [...localExperiments, ...delegatedExperiments]) {
    if (!byRun.has(experiment.run_id)) byRun.set(experiment.run_id, experiment);
  }
  const filtered = [...byRun.values()].filter((item) =>
    (!args.workload || item.workload === args.workload) &&
    (!args.provider || item.provider === args.provider || item.execution_origin === args.provider) &&
    (!args.state || item.state === args.state));
  filtered.sort((left, right) => (right.created_at || 0) - (left.created_at || 0) || right.run_id.localeCompare(left.run_id));
  const hasMore = filtered.length > limit;
  const experiments = filtered.slice(0, limit);
  const last = experiments.at(-1);
  const nextCursor = hasMore && last ? `${last.created_at}:${last.run_id}` : null;
  return { schema_version: 2, status: "ok", experiments, page: { limit, has_more: hasMore, next_cursor: nextCursor },
    ...(providerAdapterConfigured(env) ? { provider_adapter: { configured: true } } : {}) };
}
