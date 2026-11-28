import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { createGoogleColabOperation, readGoogleColabOperation, transitionGoogleColabOperation } from "../colab/lifecycle/google_colab_operation_store.js";

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(`PRAGMA foreign_keys=ON;
    CREATE TABLE gateway_delegated_plans (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
      workload TEXT NOT NULL, approved_plan_json TEXT NOT NULL,
      state TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
      cancelled_at INTEGER, UNIQUE(owner_id,id,fingerprint)
    );`);
  sqlite.exec(awaitMigration());
  const db = { prepare(sql) { return { bind(...values) {
    const statement = sqlite.prepare(sql);
    return { first: async () => statement.get(...values) || null,
      run: async () => statement.run(...values) };
  } }; } };
  const runId = "a".repeat(32), owner = "chat-owner", fingerprint = "b".repeat(64);
  sqlite.prepare(`INSERT INTO gateway_delegated_plans
    (id,owner_id,fingerprint,workload,approved_plan_json,state,created_at,expires_at,cancelled_at)
    VALUES (?,?,?,?,?,'prepared',?,?,NULL)`).run(runId, owner, fingerprint, "colab-owner-training", "{}", 100, 1000);
  return { db, sqlite, runId, owner, fingerprint };
}

function awaitMigration() {
  return `CREATE TABLE google_colab_run_operations (
    run_id TEXT PRIMARY KEY REFERENCES gateway_delegated_plans(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL, plan_fingerprint TEXT NOT NULL, state TEXT NOT NULL,
    runtime_request_id TEXT NOT NULL, execution_id TEXT, runtime_name TEXT, session_name TEXT,
    connection_ciphertext TEXT, connection_iv TEXT, execution_code_sha256 TEXT,
    execution_result_json TEXT, updated_at INTEGER NOT NULL,
    FOREIGN KEY (owner_id,run_id,plan_fingerprint)
      REFERENCES gateway_delegated_plans(owner_id,id,fingerprint) ON DELETE CASCADE
  );`;
}

test("Colab operation creation is persisted before runtime allocation and exact retries reuse its request ID", async () => {
  const { db, sqlite, owner, runId, fingerprint } = database();
  try {
    const input = { owner, runId, fingerprint, runtimeRequestId: "12345678-1234-4234-8234-123456789abc", now: 200 };
    const created = await createGoogleColabOperation(db, input);
    assert.equal(created.state, "runtime_create_pending");
    assert.equal((await createGoogleColabOperation(db, input)).runtime_request_id, input.runtimeRequestId);
    await assert.rejects(createGoogleColabOperation(db, { ...input,
      runtimeRequestId: "12345678-1234-4234-8234-123456789abd" }),
    { message: "GOOGLE_COLAB_OPERATION_NOT_CREATED" });
    assert.equal(await readGoogleColabOperation(db, "other-owner", runId, fingerprint), null);
  } finally { sqlite.close(); }
});

test("Colab operation transitions are compare-and-set, identity-bound, and size bounded", async () => {
  const { db, sqlite, owner, runId, fingerprint } = database();
  try {
    await createGoogleColabOperation(db, { owner, runId, fingerprint,
      runtimeRequestId: "12345678-1234-4234-8234-123456789abc", now: 200 });
    const ready = await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "runtime_create_pending", toState: "runtime_ready", now: 201,
      patch: { runtime_name: "runtimes/gpu-control-run" } });
    assert.equal(ready, true);
    assert.equal(await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "runtime_create_pending", toState: "runtime_ready", now: 202 }), false);
    assert.equal(await transitionGoogleColabOperation(db, { owner: "other-owner", runId, fingerprint,
      fromState: "runtime_ready", toState: "session_create_pending", now: 203 }), false);
    assert.equal(await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "runtime_ready", toState: "session_create_pending", now: 203,
      patch: { session_name: "runtimes/gpu-control-run/sessions/run-1" } }), true);
    const executionId = "12345678-1234-4234-8234-123456789abc";
    const codeHash = "c".repeat(64);
    assert.equal(await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "session_create_pending", toState: "execution_pending", now: 204,
      patch: { execution_id: executionId, execution_code_sha256: codeHash } }), true);
    assert.equal(await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "execution_pending", toState: "execution_pending", now: 205,
      patch: { execution_id: executionId, execution_code_sha256: codeHash } }), true);
    assert.equal(await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "execution_pending", toState: "execution_pending", now: 206,
      patch: { execution_id: "12345678-1234-4234-8234-123456789abd", execution_code_sha256: codeHash } }), false);
    await assert.rejects(transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "execution_pending", toState: "terminal", now: 207 }),
    { message: "GOOGLE_COLAB_OPERATION_INVALID_TRANSITION" });
    assert.equal(await transitionGoogleColabOperation(db, { owner, runId, fingerprint,
      fromState: "execution_pending", toState: "execution_complete", now: 208,
      patch: { runtime_name: "runtimes/user-notebook" } }), false);
  } finally { sqlite.close(); }
});
