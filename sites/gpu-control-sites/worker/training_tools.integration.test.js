import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { handleTrainingTool } from "./training_tools.js";

test("missing owner-training adapter journal stays uncertain and cannot resubmit", async () => {
  const runId = "a".repeat(32);
  const fingerprint = "b".repeat(64);
  const plan = { execution_kind: "owner_selected_python", run_id: runId };
  const row = {
    fingerprint,
    plan_json: JSON.stringify(plan),
    expires_at: Math.floor(Date.now() / 1000) + 600,
    cancelled_at: null,
    dispatch_claimed_at: Math.floor(Date.now() / 1000) - 1,
    dispatch_rejection: null,
    cleanup_confirmed_at: null,
  };
  const env = { MAP_TRAINING_ADMISSION_ENABLED: "true", DB: {
    prepare(sql) {
      return { bind() { return { first: async () => {
        if (sql.includes("FROM training_plans")) return row;
        if (sql.includes("FROM training_authorizations")) return null;
        throw new Error(`unexpected query: ${sql}`);
      }, run: async () => ({ meta: { changes: 0 } }) }; } };
    },
  } };
  const delegatedCalls = [];
  const delegate = async (_env, _owner, tool, args) => {
    delegatedCalls.push({ tool, args });
    return { state: "not_found" };
  };
  const services = { env, owner: "owner", delegate, isConfigured: () => true,
    getSourceToken: async () => null };

  const status = await handleTrainingTool("training_status", { run_id: runId }, services);
  assert.equal(status.machine_state.state, "uncertain");
  assert.equal(status.machine_state.provider_resource_created, "unknown");
  assert.equal(status.machine_state.cleanup_state, "unknown");
  assert.equal(status.blocking_reason, "SUBMISSION_OUTCOME_UNCONFIRMED");
  assert.match(status.human_summary, /二重実行を避けて同じrunの照合/);
  assert.deepEqual(status.next_allowed_actions, ["training_status"]);

  const cancel = await handleTrainingTool("training_cancel", { run_id: runId }, services);
  assert.equal(cancel.machine_state.state, "uncertain");
  assert.equal(cancel.machine_state.provider_resource_created, "unknown");
  assert.equal(cancel.machine_state.cleanup_state, "unknown");
  assert.equal(cancel.blocking_reason, "SUBMISSION_OUTCOME_UNCONFIRMED");

  const repeatedSubmit = await handleTrainingTool("training_submit", {
    run_id: runId, plan_fingerprint: fingerprint, approved_plan: plan,
  }, services);
  assert.equal(repeatedSubmit.machine_state.state, "dispatching");
  assert.deepEqual(delegatedCalls, [
    { tool: "training_status", args: { run_id: runId, plan_fingerprint: fingerprint, approved_plan: plan } },
    { tool: "training_cancel", args: { run_id: runId, plan_fingerprint: fingerprint, approved_plan: plan } },
  ]);
});

test("a durable terminal training result survives adapter journal loss", async () => {
  const runId = "c".repeat(32);
  const fingerprint = "d".repeat(64);
  const providerResult = { state: "succeeded", cleanup: "confirmed", gpu_used: true,
    exit_code: 0, checkpoint: { filename: "checkpoint.pt", size_bytes: 10, sha256: "e".repeat(64) },
    artifacts: [] };
  const row = { fingerprint, plan_json: JSON.stringify({ execution_kind: "owner_selected_python", run_id: runId }),
    expires_at: 1, cancelled_at: null, dispatch_claimed_at: 2, dispatch_rejection: null,
    cleanup_confirmed_at: 5, provider_result_json: JSON.stringify(providerResult) };
  const env = { DB: { prepare(sql) { return { bind(...values) { return {
    first: async () => sql.includes("FROM training_plans") ? row : null,
    run: async () => ({ meta: { changes: 0 } }),
  }; } }; } } };
  let delegateCalls = 0;
  const response = await handleTrainingTool("training_status", { run_id: runId }, {
    env, owner: "owner", delegate: async () => { delegateCalls++; throw new Error("must use D1 result"); },
    isConfigured: () => false,
  });
  assert.equal(response.machine_state.state, "succeeded");
  assert.equal(response.machine_state.gpu_used, true);
  assert.equal(delegateCalls, 0);

});

test("MAP terminal status persists the adapter cleanup_state and native checkpoint result", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    db.exec(`CREATE TABLE training_plans (
      owner_id TEXT NOT NULL, id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, plan_json TEXT NOT NULL,
      expires_at INTEGER NOT NULL, cancelled_at INTEGER, dispatch_claimed_at INTEGER,
      dispatch_rejection TEXT, cleanup_confirmed_at INTEGER, provider_result_json TEXT
    );
    CREATE TABLE training_authorizations (
      plan_id TEXT, owner_id TEXT, fingerprint TEXT, authorization_id TEXT, authorization_source TEXT,
      authorization_reference TEXT, decision_record_id TEXT, authorized_by TEXT, control_plane_sha TEXT,
      target_repository TEXT, target_sha TEXT, image_digest TEXT, provider TEXT, provider_resource_id TEXT,
      gpu_count INTEGER, runtime_seconds INTEGER, max_cost_microusd INTEGER, authorized_at INTEGER,
      expires_at INTEGER, consumed_at INTEGER
    );`);
    const runId = "a".repeat(32);
    const fingerprint = "b".repeat(64);
    db.prepare(`INSERT INTO training_plans
      (owner_id,id,fingerprint,plan_json,expires_at,dispatch_claimed_at)
      VALUES (?,?,?,?,?,?)`).run("owner", runId, fingerprint,
        JSON.stringify({ execution_kind: "map_training" }), Math.floor(Date.now() / 1000) + 300, 1);
    const DB = { prepare(sql) { return { bind(...values) { const statement = db.prepare(sql); return {
      first: async () => statement.get(...values),
      run: async () => { const result = statement.run(...values); return { meta: { changes: Number(result.changes) } }; },
    }; } }; } };
    const response = await handleTrainingTool("training_status", { run_id: runId }, {
      env: { DB }, owner: "owner", isConfigured: () => true,
      delegate: async () => ({ state: "succeeded", cleanup_state: "confirmed", gpu_used: true,
        steps: 100, dataset: "papers", run_name: "map44m", source_sha: "c".repeat(40),
        image_digest: "sha256:" + "d".repeat(64),
        checkpoint: { filename: "step-000000100-abcdef12.pt", size_bytes: 2048, sha256: "e".repeat(64) } }),
    });
    assert.equal(response.machine_state.state, "succeeded");
    assert.equal(response.machine_state.cleanup_state, "confirmed");
    const stored = db.prepare("SELECT provider_result_json,cleanup_confirmed_at FROM training_plans WHERE id=?")
      .get(runId);
    assert.equal(stored.cleanup_confirmed_at > 0, true);
    assert.deepEqual(JSON.parse(stored.provider_result_json), {
      state: "succeeded", cleanup: "confirmed", execution_kind: "map_training", gpu_used: true,
      steps: 100, dataset: "papers", run_name: "map44m", source_sha: "c".repeat(40),
      image_digest: "sha256:" + "d".repeat(64),
      checkpoint: { filename: "step-000000100-abcdef12.pt", size_bytes: 2048, sha256: "e".repeat(64) },
    });
  } finally { db.close(); }
});

test("MAP runtime-limit failures keep one checkpoint-recovery action available", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    db.exec(`CREATE TABLE training_plans (
      owner_id TEXT NOT NULL, id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, plan_json TEXT NOT NULL,
      expires_at INTEGER NOT NULL, cancelled_at INTEGER, dispatch_claimed_at INTEGER,
      dispatch_rejection TEXT, cleanup_confirmed_at INTEGER, provider_result_json TEXT
    );
    CREATE TABLE training_authorizations (
      plan_id TEXT, owner_id TEXT, fingerprint TEXT, authorization_id TEXT, authorization_source TEXT,
      authorization_reference TEXT, decision_record_id TEXT, authorized_by TEXT, control_plane_sha TEXT,
      target_repository TEXT, target_sha TEXT, image_digest TEXT, provider TEXT, provider_resource_id TEXT,
      gpu_count INTEGER, runtime_seconds INTEGER, max_cost_microusd INTEGER, authorized_at INTEGER,
      expires_at INTEGER, consumed_at INTEGER
    );`);
    const runId = "f".repeat(32);
    const fingerprint = "e".repeat(64);
    const plan = { execution_kind: "map_training", run_id: runId };
    const result = { state: "failed", cleanup: "confirmed", failure_code: "TRAINING_RUNTIME_LIMIT" };
    db.prepare(`INSERT INTO training_plans
      (owner_id,id,fingerprint,plan_json,expires_at,dispatch_claimed_at,cleanup_confirmed_at,provider_result_json)
      VALUES (?,?,?,?,?,?,?,?)`).run("owner", runId, fingerprint, JSON.stringify(plan),
        Math.floor(Date.now() / 1000) + 300, 1, 2, JSON.stringify(result));
    const DB = { prepare(sql) { return { bind(...values) { const statement = db.prepare(sql); return {
      first: async () => statement.get(...values),
      run: async () => { const stored = statement.run(...values); return { meta: { changes: Number(stored.changes) } }; },
    }; } }; } };
    const calls = [];
    const services = { env: { DB }, owner: "owner", isConfigured: () => true,
      delegate: async (_env, _owner, tool, args) => {
        calls.push({ tool, args });
        return { state: "succeeded", checkpoint_chunk: { offset: 0, eof: true, data_base64: "YQ==" } };
      } };
    const status = await handleTrainingTool("training_status", { run_id: runId }, services);
    assert.equal(status.machine_state.state, "failed");
    assert.deepEqual(status.next_allowed_actions, ["training_checkpoint"]);
    const checkpoint = await handleTrainingTool("training_checkpoint", { run_id: runId,
      offset: 0, max_bytes: 1024 }, services);
    assert.equal(checkpoint.machine_state.eof, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].tool, "training_checkpoint");
    assert.deepEqual(calls[0].args.approved_plan, { ...plan, run_id: runId });
  } finally { db.close(); }
});
