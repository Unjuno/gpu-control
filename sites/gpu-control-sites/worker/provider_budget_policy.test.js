import assert from "node:assert/strict";
import test from "node:test";

import { readProviderBudgetPolicy } from "./provider_budget_policy.js";

function database({ modalCpuMonthly = 30_000_000, modalGpuMonthly = 1_000_000, freePolicies } = {}) {
  const result = (value) => ({ first: async () => value, all: async () => ({ results: value }) });
  return { prepare(sql) {
    if (sql.includes("FROM provider_budget_policies")) return result([
      { provider: "modal_cpu", monthly_limit_microusd: modalCpuMonthly, per_run_limit_microusd: 10_000 },
      { provider: "runpod_gpu", monthly_limit_microusd: null, per_run_limit_microusd: 1_000_000 },
    ]);
    if (sql.includes("FROM modal_gpu_budget_policy")) return result({
      monthly_limit_microusd: modalGpuMonthly, per_run_limit_microusd: 10_000, admission_enabled: 1,
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
    { provider: "modal_cpu", policy_available: true, scope: "registered_workload_reservation",
      monthly_limit_usd: "30.00", per_run_limit_usd: "0.01" },
    { provider: "modal_gpu", policy_available: true, scope: "registered_workload_reservation", monthly_limit_usd: "1.00",
      per_run_limit_usd: "0.01", admission_enabled: true },
    { provider: "runpod_gpu", policy_available: true, scope: "registered_workload_reservation",
      monthly_limit_usd: null, per_run_limit_usd: "1.00" },
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

test("Modal GPU cannot claim an unbounded monthly limit when its policy is malformed", async () => {
  const result = await readProviderBudgetPolicy(database({ modalGpuMonthly: null }));
  assert.equal(result.state, "unavailable");
  assert.ok(result.provider_budgets.every((policy) => !Object.hasOwn(policy, "per_run_limit_usd")));
});
