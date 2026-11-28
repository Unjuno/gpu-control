import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import { prepareModalComputeBudgetReservation, readProviderBudgetPolicy, reserveProviderBudget } from "./provider_budget_policy.js";

function database({ modalMonthly = 30_000_000, modalReserved = 0, freePolicies } = {}) {
  const result = (value) => ({ first: async () => value, all: async () => ({ results: value }), bind() { return this; } });
  return { prepare(sql) {
    if (sql.includes("FROM provider_budget_policies")) return result({
      provider: "runpod_gpu", monthly_limit_microusd: null, per_run_limit_microusd: 1_000_000,
    });
    if (sql.includes("FROM modal_compute_budget_policy")) return result({
      monthly_limit_microusd: modalMonthly, per_run_limit_microusd: 1_000_000,
    });
    if (sql.includes("FROM modal_compute_budget_reservations")) return result({ monthly_reserved_microusd: modalReserved });
    if (sql.includes("FROM modal_gpu_admission_policy")) return result({
      admission_enabled: 1,
    });
    if (sql.includes("FROM provider_free_policies")) return result(freePolicies || [
      { provider: "kaggle", max_cost_microusd: 0, paid_fallback_allowed: 0 },
      { provider: "huggingface_space", max_cost_microusd: 0, paid_fallback_allowed: 0 },
    ]);
    throw new Error("unexpected query");
  } };
}

test("capability budget terms come from the same provider-specific D1 policies used by reservation", async () => {
  const result = await readProviderBudgetPolicy(database());
  assert.equal(result.state, "ready");
  assert.deepEqual(result.provider_budgets, [
    { provider: "modal", policy_available: true, scope: "modal_compute_shared_across_routes",
      monthly_limit_usd: "30.00", per_run_limit_usd: "1.00", monthly_limit_microusd: 30_000_000,
      per_run_limit_microusd: 1_000_000, monthly_reserved_microusd: 0, monthly_reserved_usd: "0.00",
      monthly_remaining_microusd: 30_000_000, monthly_remaining_usd: "30.00",
      routes: ["modal_cpu", "modal_gpu"], modal_gpu_admission_enabled: true },
    { provider: "runpod_gpu", policy_available: true, scope: "provider_reservation",
      monthly_limit_usd: null, per_run_limit_usd: "1.00", monthly_limit_microusd: null,
      per_run_limit_microusd: 1_000_000 },
    { provider: "kaggle", policy_available: true, scope: "registered_free_workload_policy", monthly_limit_usd: "0.00",
      per_run_limit_usd: "0.00", paid_fallback_allowed: false },
    { provider: "huggingface_space", policy_available: true, scope: "registered_free_workload_policy", monthly_limit_usd: "0.00",
      per_run_limit_usd: "0.00", paid_fallback_allowed: false },
  ]);
});

test("missing or contradictory policy fails closed without guessed dollar amounts", async () => {
  const result = await readProviderBudgetPolicy(database({ freePolicies: [
    { provider: "kaggle", max_cost_microusd: 0, paid_fallback_allowed: 1 },
  ] }));
  assert.equal(result.state, "unavailable");
  assert.ok(result.provider_budgets.every((policy) => !Object.hasOwn(policy, "monthly_limit_usd") &&
    policy.blocker === "PROVIDER_BUDGET_POLICY_UNAVAILABLE"));
});

test("provider budget reservation enforces its per-run policy and exact retry binding", async () => {
  const sqlite = new DatabaseSync(":memory:");
  try {
    sqlite.exec(`CREATE TABLE provider_budget_policies (
        provider TEXT PRIMARY KEY, monthly_limit_microusd INTEGER, per_run_limit_microusd INTEGER);
      INSERT INTO provider_budget_policies VALUES ('runpod_gpu', NULL, 1000000);
      CREATE TABLE provider_budget_reservations (
        run_id TEXT PRIMARY KEY, provider TEXT, period_key TEXT, reserved_microusd INTEGER, created_at INTEGER);`);
    const db = { prepare(sql) {
      const statement = sqlite.prepare(sql);
      return { bind(...values) { return {
        run: async () => {
          const result = statement.run(...values);
          return { meta: { changes: Number(result.changes) } };
        },
        first: async () => statement.get(...values) || null,
      }; } };
    } };
    const reservation = { runId: "a".repeat(32), provider: "runpod_gpu",
      requestedMicrousd: 1_000_000, now: 1_798_000_000 };
    assert.equal(await reserveProviderBudget({ DB: db }, reservation), true);
    assert.equal(await reserveProviderBudget({ DB: db }, reservation), true,
      "an exact retry observes the existing reservation");
    assert.equal(await reserveProviderBudget({ DB: db }, { ...reservation, requestedMicrousd: 900_000 }), false,
      "the same run cannot silently change its reserved amount");
    assert.equal(await reserveProviderBudget({ DB: db }, { ...reservation,
      runId: "b".repeat(32), requestedMicrousd: 1_000_001 }), false,
      "a new run cannot exceed the provider per-run policy");
    assert.equal(await reserveProviderBudget({ DB: db }, { ...reservation,
      runId: "c".repeat(32), provider: "unknown" }), false,
      "a provider without a policy cannot reserve budget");
  } finally {
    sqlite.close();
  }
});

test("Modal compute policy must match the bounded monthly and per-run limits", async () => {
  const result = await readProviderBudgetPolicy(database({ modalMonthly: 0 }));
  assert.equal(result.state, "unavailable");
  assert.ok(result.provider_budgets.every((policy) => !Object.hasOwn(policy, "per_run_limit_usd")));
});

test("Modal capabilities expose reserved and remaining Sites budget without calling it billed usage", async () => {
  const result = await readProviderBudgetPolicy(database({ modalReserved: 29_990_000 }));
  const modal = result.provider_budgets.find((item) => item.provider === "modal");
  assert.equal(modal.monthly_reserved_microusd, 29_990_000);
  assert.equal(modal.monthly_reserved_usd, "29.99");
  assert.equal(modal.monthly_remaining_microusd, 10_000);
  assert.equal(modal.monthly_remaining_usd, "0.01");
});

test("Modal CPU, fixed GPU, and training share one atomic monthly reservation ledger", async () => {
  const sqlite = new DatabaseSync(":memory:");
  try {
    sqlite.exec(`CREATE TABLE modal_compute_budget_policy (
        scope TEXT PRIMARY KEY, monthly_limit_microusd INTEGER, per_run_limit_microusd INTEGER);
      INSERT INTO modal_compute_budget_policy VALUES ('workspace', 1000000, 1000000);
      CREATE TABLE modal_gpu_admission_policy (
        scope TEXT PRIMARY KEY, admission_enabled INTEGER);
      INSERT INTO modal_gpu_admission_policy VALUES ('workspace', 1);
      CREATE TABLE modal_compute_budget_reservations (
        run_id TEXT PRIMARY KEY, source TEXT, plan_fingerprint TEXT, period_key TEXT,
        reserved_microusd INTEGER, created_at INTEGER);`);
    const db = { prepare(sql) {
      const statement = sqlite.prepare(sql);
      return { bind(...values) { return {
        run: async () => {
          const result = statement.run(...values);
          return { meta: { changes: Number(result.changes) } };
        },
        first: async () => statement.get(...values) || null,
      }; } };
    } };
    const reserve = async (id, source, amount, month = "2026-11") => {
      const reservation = { runId: id.toString(16).padStart(32, "0"), source,
        fingerprint: id.toString(16).padStart(64, "0"), periodKey: month,
        requestedMicrousd: amount, now: 1_798_000_000 };
      const inserted = await prepareModalComputeBudgetReservation(db, reservation).run();
      const existing = await db.prepare(`SELECT source, plan_fingerprint, period_key, reserved_microusd
        FROM modal_compute_budget_reservations WHERE run_id=?`).bind(reservation.runId).first();
      return inserted.meta.changes === 1 || (existing?.source === source &&
        existing.plan_fingerprint === reservation.fingerprint && existing.period_key === month &&
        existing.reserved_microusd === amount);
    };
    assert.equal(await reserve(1, "modal_cpu", 750_000), true);
    assert.equal(await reserve(2, "map_training", 250_000), true);
    assert.equal(await reserve(1, "modal_cpu", 750_000), true, "exact retries are idempotent");
    assert.equal(await reserve(1, "modal_gpu_canary", 750_000), false,
      "a run ID cannot be reused for a different Modal workload");
    assert.equal(await reserve(3, "modal_gpu_canary", 10_000), false,
      "the fixed GPU route cannot bypass CPU and training reservations");
    assert.equal(await reserve(4, "owner_selected_training", 10_000), false,
      "a route cannot exceed the remaining account reservation budget");
    assert.equal(await reserve(5, "owner_selected_training", 1_000_001), false,
      "a single run cannot exceed its provider ceiling");
    assert.equal(sqlite.prepare("SELECT SUM(reserved_microusd) AS total FROM modal_compute_budget_reservations")
      .get().total, 1_000_000);
  } finally {
    sqlite.close();
  }
});
