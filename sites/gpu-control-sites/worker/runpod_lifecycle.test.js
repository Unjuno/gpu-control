import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { submitRunpodExperiment, synchronizeRunpodExperiment, validRunpodApprovedPlan } from "./runpod_lifecycle.js";
import { prepareRunpodExperiment, RUNPOD_REPOSITORY, RUNPOD_WORKLOAD } from "./runpod_plan.js";

const MIGRATIONS = new URL("../drizzle/", import.meta.url);
const SOURCE = "1".repeat(40);
const IMAGE = `ghcr.io/unjuno/gpu-control-runpod-canary@sha256:${"a".repeat(64)}`;
const KEY = Buffer.from(Array.from({ length: 32 }, (_, i) => i)).toString("base64");

class D1 {
  constructor(raw) { this.raw = raw; }
  prepare(sql) {
    let parameters = []; const raw = this.raw;
    const statement = { sql, get parameters() { return parameters; },
      bind(...values) { parameters = values; return statement; },
      first() { return raw.prepare(sql).get(...parameters) ?? null; },
      all() { return { results: raw.prepare(sql).all(...parameters) }; },
      run() { return { meta: raw.prepare(sql).run(...parameters) }; } };
    return statement;
  }
  batch(statements) {
    this.raw.exec("BEGIN IMMEDIATE");
    try {
      const result = statements.map((statement) => ({ results: this.raw.prepare(statement.sql).all(...statement.parameters) }));
      this.raw.exec("COMMIT"); return result;
    } catch (error) { this.raw.exec("ROLLBACK"); throw error; }
  }
}

function environment() {
  const raw = new DatabaseSync(":memory:"); raw.exec("PRAGMA foreign_keys=ON");
  for (const file of readdirSync(MIGRATIONS).filter((name) => name.endsWith(".sql")).sort()) {
    raw.exec(readFileSync(new URL(file, MIGRATIONS), "utf8"));
  }
  return { raw, env: { DB: new D1(raw), RUNPOD_API_KEY: "rpa_test_abcdefghijklmnopqrstuvwxyz",
    RUNPOD_WORKLOAD_IMAGE: IMAGE, RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation",
    RUNPOD_WORKLOAD_SOURCE_SHA: SOURCE, RUNPOD_GPU_ADMISSION_ENABLED: "true",
    RUNPOD_STATE_KEY_B64: KEY, RUNPOD_ACCOUNT_SCOPE_ID: "primary",
    RUNPOD_ACCOUNT_SCOPE_HMAC_KEY_B64: KEY } };
}

class FakeRunpod {
  constructor() { this.creates = 0; this.terminated = 0; this.podId = "pod-test-123"; }
  async getVerifiedOffer() { return { gpuId: "NVIDIA RTX 2000 Ada Generation", cloud: "SECURE", gpuCount: 1,
    hourlyPriceUsd: 0.24, availability: "HIGH", dataCenterId: "US-KS-2", checkedAt: 100,
    validForSeconds: 300, source: "runpod-rest-v2-catalog" }; }
  async createPod(input) { this.creates += 1; this.name = `gpu-control-${input.runId.slice(0, 12)}`; return { id: this.podId, name: this.name, image: IMAGE,
    cloud: "SECURE", gpu: { id: "NVIDIA RTX 2000 Ada Generation", count: 1 }, ports: [], status: "RUNNING" }; }
  async getPod() { return { id: this.podId, name: this.name, image: IMAGE,
    cloud: "SECURE", gpu: { id: "NVIDIA RTX 2000 Ada Generation", count: 1 }, ports: [], status: "RUNNING" }; }
  async getPodLogSnapshot() { return []; }
  async terminatePod() { this.terminated += 1; }
}

test("Runpod submit is idempotent and cancellation confirms cleanup before releasing the account", async () => {
  const { raw, env } = environment(); const client = new FakeRunpod();
  try {
    const prepared = await prepareRunpodExperiment(env, "site-owner", { repository: RUNPOD_REPOSITORY,
      commit: SOURCE, workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: 30,
      max_cost_usd: "1.00", idempotency_key: "runpod-test-one" }, { client, now: 100 });
    assert.equal(validRunpodApprovedPlan(prepared.provider_approved_plan), true);
    const args = { run_id: prepared.run_id, plan_fingerprint: prepared.plan_fingerprint,
      provider_approved_plan: prepared.provider_approved_plan };
    const first = await submitRunpodExperiment(env, "site-owner", args,
      { client, now: 101, reserveBudget: async () => true });
    assert.equal(first.status, "pending"); assert.equal(client.creates, 1);
    const replay = await submitRunpodExperiment(env, "site-owner", args,
      { client, now: 102, reserveBudget: async () => true });
    assert.equal(replay.status, "pending"); assert.equal(client.creates, 1);
    const cancelled = await synchronizeRunpodExperiment(env, "site-owner", prepared.run_id, { client, cancel: true });
    assert.equal(cancelled.state, "cancelled"); assert.equal(cancelled.cleanup_state, "confirmed");
    assert.equal(client.terminated, 1);
    assert.equal(raw.prepare("SELECT state FROM provider_account_leases").get().state, "released");
  } finally { raw.close(); }
});
