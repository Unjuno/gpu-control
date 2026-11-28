import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import { readDelegatedPlan, persistProviderAdapterObservation, publicProviderAdapterResponse } from "./provider_adapter_run_store.js";
import { WORKLOADS } from "./workload_registry.js";

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(`CREATE TABLE gateway_delegated_plans (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
    workload TEXT NOT NULL, approved_plan_json TEXT NOT NULL, state TEXT NOT NULL,
    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, provider_handle_json TEXT,
    provider_state TEXT, provider_response_json TEXT, updated_at INTEGER,
    cancelled_at INTEGER, terminal_at INTEGER, source_run_id TEXT, submit_attempted_at INTEGER
  )`);
  const db = { prepare(sql) {
    return { bind(...values) {
      const statement = sqlite.prepare(sql);
      return {
        first: async () => statement.get(...values) || null,
        all: async () => ({ results: statement.all(...values) }),
        run: async () => statement.run(...values),
      };
    } };
  } };
  const insert = sqlite.prepare(`INSERT INTO gateway_delegated_plans
    (id, owner_id, fingerprint, workload, approved_plan_json, state, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?, 'submitted', 1, 9999999999)`);
  insert.run("1".repeat(32), "owner-a", "a".repeat(64), WORKLOADS.kaggle_training.id, "{}");
  return { db, sqlite };
}

test("delegated plan lookup stays owner-scoped and returns only supported workloads", async () => {
  const { db, sqlite } = database();
  try {
    assert.equal((await readDelegatedPlan({ DB: db }, "owner-a", "1".repeat(32))).id, "1".repeat(32));
    assert.equal(await readDelegatedPlan({ DB: db }, "owner-b", "1".repeat(32)), null);
    assert.equal(await readDelegatedPlan({ DB: db }, "owner-a", "2".repeat(32)), null);
  } finally { sqlite.close(); }
});

test("provider observations are bounded, persisted owner-scoped, and handles are redacted publicly", async () => {
  const { db, sqlite } = database();
  try {
    const response = { status: "pending", machine_state: { state: "running",
      provider_handle: { provider: "kaggle", job_id: "job-123" }, result: { step: 3 } } };
    await persistProviderAdapterObservation({ DB: db }, "owner-a", "1".repeat(32), response);
    const stored = await readDelegatedPlan({ DB: db }, "owner-a", "1".repeat(32));
    assert.equal(stored.provider_state, "running");
    assert.deepEqual(JSON.parse(stored.provider_handle_json), response.machine_state.provider_handle);
    assert.deepEqual(JSON.parse(stored.provider_response_json), response);
    const publicResponse = publicProviderAdapterResponse(response);
    assert.equal(publicResponse.machine_state.provider_handle, undefined);
    assert.equal(response.machine_state.provider_handle.job_id, "job-123");
  } finally { sqlite.close(); }
});

test("malformed handles and oversized observations are rejected before persistence", async () => {
  const { db, sqlite } = database();
  try {
    await assert.rejects(persistProviderAdapterObservation({ DB: db }, "owner-a", "1".repeat(32),
      { machine_state: { provider_handle: [] } }), { message: "GATEWAY_DELEGATION_INVALID_RESPONSE" });
    await assert.rejects(persistProviderAdapterObservation({ DB: db }, "owner-a", "1".repeat(32),
      { machine_state: { result: "x".repeat(64 * 1024) } }), { message: "GATEWAY_DELEGATION_RESPONSE_TOO_LARGE" });
    const stored = await readDelegatedPlan({ DB: db }, "owner-a", "1".repeat(32));
    assert.equal(stored.provider_state, null);
    assert.equal(stored.provider_response_json, null);
  } finally { sqlite.close(); }
});
