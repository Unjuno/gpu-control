import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { loadApprovedTrainingPlan, persistTrainingTerminalResult } from "./training_plan_state.js";

function dbBinding(db) {
  return { prepare(sql) {
    const statement = db.prepare(sql);
    return { bind(...values) { return {
      first: async () => statement.get(...values),
      run: async () => {
        const result = statement.run(...values);
        return { meta: { changes: Number(result.changes) } };
      },
    }; } };
  } };
}

test("terminal provider result is owner/fingerprint bound, write-once, and size bounded", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    db.exec(`CREATE TABLE training_plans (
      owner_id TEXT NOT NULL, id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
      plan_json TEXT NOT NULL, dispatch_claimed_at INTEGER, cleanup_confirmed_at INTEGER,
      provider_result_json TEXT CHECK (provider_result_json IS NULL OR length(provider_result_json) <= 65536)
    )`);
    const runId = "a".repeat(32);
    const fingerprint = "b".repeat(64);
    db.prepare(`INSERT INTO training_plans (owner_id,id,fingerprint,plan_json,dispatch_claimed_at)
      VALUES (?,?,?,?,?)`).run("owner", runId, fingerprint,
        JSON.stringify({ repository: "owner/project", commit: "c".repeat(40) }), 1);
    const DB = dbBinding(db);
    const result = { state: "succeeded", cleanup: "confirmed", gpu_used: true, exit_code: 0,
      checkpoint: { filename: "checkpoint.pt", size_bytes: 5, sha256: "d".repeat(64) },
      metrics: { filename: "metrics.json", size_bytes: 2, sha256: "e".repeat(64), values: { loss: 0.5 } },
      artifacts: [] };
    assert.equal(await persistTrainingTerminalResult(DB, "owner", runId, fingerprint,
      { ...result, cleanup: "pending" }, 10), false);
    assert.equal(await persistTrainingTerminalResult(DB, "other-owner", runId, fingerprint, result, 10), false);
    assert.equal(await persistTrainingTerminalResult(DB, "owner", runId, "e".repeat(64), result, 10), false);
    assert.equal(await persistTrainingTerminalResult(DB, "owner", runId, fingerprint,
      { ...result, output: "x".repeat(8193) }, 10), false);
    assert.equal(await persistTrainingTerminalResult(DB, "owner", runId, fingerprint, result, 10), true);
    const stored = db.prepare("SELECT provider_result_json,cleanup_confirmed_at FROM training_plans WHERE id=?")
      .get(runId);
    assert.deepEqual(JSON.parse(stored.provider_result_json), result);
    assert.equal(stored.cleanup_confirmed_at, 10);
    assert.equal(await persistTrainingTerminalResult(DB, "owner", runId, fingerprint,
      { ...result, state: "failed" }, 11), false, "conflicting terminal observations cannot overwrite the first");
    assert.equal((await loadApprovedTrainingPlan(DB, "owner", runId, fingerprint)).run_id, runId);
    await assert.rejects(loadApprovedTrainingPlan(DB, "other-owner", runId, fingerprint),
      { message: "RUN_NOT_FOUND" });
  } finally {
    db.close();
  }
});

test("MAP terminal result keeps its native checkpoint contract and cleanup evidence", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    db.exec(`CREATE TABLE training_plans (
      owner_id TEXT NOT NULL, id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
      plan_json TEXT NOT NULL, dispatch_claimed_at INTEGER, cleanup_confirmed_at INTEGER,
      provider_result_json TEXT CHECK (provider_result_json IS NULL OR length(provider_result_json) <= 65536)
    )`);
    const runId = "a".repeat(32);
    const fingerprint = "b".repeat(64);
    db.prepare(`INSERT INTO training_plans (owner_id,id,fingerprint,plan_json,dispatch_claimed_at)
      VALUES (?,?,?,?,?)`).run("owner", runId, fingerprint,
        JSON.stringify({ execution_kind: "map_training" }), 1);
    const result = { execution_kind: "map_training", state: "succeeded", cleanup: "confirmed",
      gpu_used: true, steps: 100, dataset: "papers", run_name: "map44m",
      source_sha: "c".repeat(40), image_digest: "sha256:" + "d".repeat(64),
      checkpoint: { filename: "step-000000100-abcdef12.pt", size_bytes: 2048, sha256: "e".repeat(64) } };
    assert.equal(await persistTrainingTerminalResult(dbBinding(db), "owner", runId, fingerprint, result, 10), true);
    const stored = db.prepare("SELECT provider_result_json,cleanup_confirmed_at FROM training_plans WHERE id=?")
      .get(runId);
    assert.deepEqual(JSON.parse(stored.provider_result_json), result);
    assert.equal(stored.cleanup_confirmed_at, 10);
    assert.equal(await persistTrainingTerminalResult(dbBinding(db), "owner", runId, fingerprint,
      { ...result, checkpoint: { ...result.checkpoint, filename: "checkpoint.pt" } }, 11), false);
  } finally { db.close(); }
});
