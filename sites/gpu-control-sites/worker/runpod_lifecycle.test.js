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
    RUNPOD_SERVERLESS_ENDPOINT_ID: "endpoint_test_123", RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.240000",
    RUNPOD_SERVERLESS_GPU_POOL_ID: "ADA_24",
    RUNPOD_WORKLOAD_SOURCE_SHA: SOURCE, RUNPOD_WORKLOAD_ADMISSION_ENABLED: "true",
    RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED: "true",
    RUNPOD_STATE_KEY_B64: KEY, RUNPOD_ACCOUNT_SCOPE_ID: "primary",
    RUNPOD_ACCOUNT_SCOPE_HMAC_KEY_B64: KEY } };
}

test("Runpod submit fails closed when live completion transport is not verified", async () => {
  const { raw, env } = environment(); const client = new FakeRunpod();
  try {
    const prepared = await prepareRunpodExperiment(env, "site-owner", { repository: RUNPOD_REPOSITORY,
      commit: SOURCE, workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: 30,
      max_cost_usd: "1.00", idempotency_key: "runpod-unverified-transport" }, { client, now: 100 });
    env.RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED = "false";
    const result = await submitRunpodExperiment(env, "site-owner", {
      run_id: prepared.run_id, plan_fingerprint: prepared.plan_fingerprint,
      provider_approved_plan: prepared.provider_approved_plan,
    }, { client, now: 101, reserveBudget: async () => true });
    assert.equal(result.status, "blocked");
    assert.equal(result.blocking_reason, "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED");
    assert.equal(client.creates, 0);
    assert.equal(raw.prepare("SELECT COUNT(*) AS count FROM runs").get().count, 0);
  } finally { raw.close(); }
});

class FakeRunpod {
  constructor() { this.creates = 0; this.terminated = 0; this.jobId = "job-test-123"; }
  async getVerifiedOffer() { return { gpuId: "NVIDIA RTX 2000 Ada Generation", cloud: "SERVERLESS", gpuCount: 1,
    hourlyPriceUsd: 0.24, availability: "CONFIGURED", dataCenterId: "endpoint_test_123", checkedAt: 100,
    validForSeconds: 300, source: "runpod-serverless-endpoint-config" }; }
  async submitJob() { this.creates += 1; return { id: this.jobId, status: "IN_QUEUE" }; }
  async getJob() { return { id: this.jobId, status: "IN_PROGRESS" }; }
  async cancelJob() { this.terminated += 1; return { id: this.jobId, status: "CANCELLED" }; }
  async getSubmissionReceipt() { return null; }
}

test("an ambiguous relay response recovers the one claimed provider job without resubmitting", async () => {
  const { raw, env } = environment(); const client = new FakeRunpod();
  let receiptReady = false;
  client.submitJob = async () => { client.creates += 1; throw new Error("lost response"); };
  client.getSubmissionReceipt = async () => receiptReady ? { id: client.jobId, status: "IN_QUEUE" } : null;
  try {
    const prepared = await prepareRunpodExperiment(env, "site-owner", { repository: RUNPOD_REPOSITORY,
      commit: SOURCE, workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: 30,
      max_cost_usd: "1.00", idempotency_key: "runpod-receipt-recovery" }, { client, now: 100 });
    const args = { run_id: prepared.run_id, plan_fingerprint: prepared.plan_fingerprint,
      provider_approved_plan: prepared.provider_approved_plan };
    await submitRunpodExperiment(env, "site-owner", args, { client, now: 101, reserveBudget: async () => true });
    receiptReady = true;
    const recovered = await synchronizeRunpodExperiment(env, "site-owner", prepared.run_id, { client });
    assert.equal(recovered.provider_job_id, client.jobId);
    assert.equal(recovered.provider_phase, "terminal");
    assert.equal(recovered.cleanup_state, "confirmed");
    assert.equal(client.creates, 1);
    assert.equal(client.terminated, 1);
    assert.equal(raw.prepare("SELECT state FROM provider_account_leases").get().state, "released");
  } finally { raw.close(); }
});

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

test("Runpod submit does not depend on a chat-driven cleanup heartbeat", async () => {
  const { raw, env } = environment(); const client = new FakeRunpod();
  try {
    const prepared = await prepareRunpodExperiment(env, "site-owner", { repository: RUNPOD_REPOSITORY,
      commit: SOURCE, workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: 30,
      max_cost_usd: "1.00", idempotency_key: "runpod-stale-heartbeat" }, { client, now: 100 });
    const result = await submitRunpodExperiment(env, "site-owner", {
      run_id: prepared.run_id, plan_fingerprint: prepared.plan_fingerprint,
      provider_approved_plan: prepared.provider_approved_plan,
    }, { client, now: 101, reserveBudget: async () => true });
    assert.equal(result.status, "pending");
    assert.equal(client.creates, 1);
  } finally { raw.close(); }
});

test("an ambiguous Serverless submit is never retried and releases after provider TTL", async () => {
  const { raw, env } = environment(); const client = new FakeRunpod();
  client.submitJob = async () => { client.creates += 1; throw new Error("lost response"); };
  try {
    const prepared = await prepareRunpodExperiment(env, "site-owner", { repository: RUNPOD_REPOSITORY,
      commit: SOURCE, workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: 30,
      max_cost_usd: "1.00", idempotency_key: "runpod-ambiguous-submit" }, { client, now: 100 });
    const args = { run_id: prepared.run_id, plan_fingerprint: prepared.plan_fingerprint,
      provider_approved_plan: prepared.provider_approved_plan };
    const submitted = await submitRunpodExperiment(env, "site-owner", args,
      { client, now: 101, reserveBudget: async () => true });
    assert.equal(submitted.machine_state.provider_phase, "uncertain");
    assert.equal(client.creates, 1);
    const reconciled = await synchronizeRunpodExperiment(env, "site-owner", prepared.run_id, { client });
    assert.equal(reconciled.state, "failed");
    assert.equal(reconciled.failure_code, "RUNPOD_AMBIGUOUS_SUBMIT_TTL_ELAPSED");
    assert.equal(client.creates, 1);
    assert.equal(raw.prepare("SELECT state FROM provider_account_leases").get().state, "released");
  } finally { raw.close(); }
});

test("an unavailable relay receipt cannot strand an ambiguous run after provider TTL", async () => {
  const { raw, env } = environment(); const client = new FakeRunpod();
  client.submitJob = async () => { client.creates += 1; throw new Error("lost response"); };
  client.getSubmissionReceipt = async () => { throw new Error("receipt unavailable"); };
  try {
    const prepared = await prepareRunpodExperiment(env, "site-owner", { repository: RUNPOD_REPOSITORY,
      commit: SOURCE, workload: RUNPOD_WORKLOAD, parameters: {}, runtime_seconds: 30,
      max_cost_usd: "1.00", idempotency_key: "runpod-receipt-unavailable" }, { client, now: 100 });
    const submitted = await submitRunpodExperiment(env, "site-owner", {
      run_id: prepared.run_id, plan_fingerprint: prepared.plan_fingerprint,
      provider_approved_plan: prepared.provider_approved_plan,
    }, { client, now: 101, reserveBudget: async () => true });
    assert.equal(submitted.machine_state.provider_phase, "uncertain");
    const reconciled = await synchronizeRunpodExperiment(env, "site-owner", prepared.run_id, { client });
    assert.equal(reconciled.state, "failed");
    assert.equal(reconciled.failure_code, "RUNPOD_AMBIGUOUS_SUBMIT_TTL_ELAPSED");
    assert.equal(client.creates, 1);
    assert.equal(raw.prepare("SELECT state FROM provider_account_leases").get().state, "released");
  } finally { raw.close(); }
});
