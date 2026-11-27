const PROVIDERS = Object.freeze([
  "modal_cpu", "modal_gpu", "runpod_gpu", "kaggle", "huggingface_space",
]);

export function usdFromMicrousd(value) {
  if (!Number.isSafeInteger(value) || value < 0) throw new TypeError("invalid_provider_budget_policy");
  const amount = BigInt(value);
  const whole = amount / 1_000_000n;
  const fractional = (amount % 1_000_000n).toString().padStart(6, "0").replace(/0+$/, "");
  return `${whole}.${fractional ? fractional.padEnd(2, "0") : "00"}`;
}

function unavailable() {
  return { schema_version: 1, state: "unavailable", provider_budgets: PROVIDERS.map((provider) => ({
    provider, policy_available: false, blocker: "PROVIDER_BUDGET_POLICY_UNAVAILABLE",
  })) };
}

function rows(result) {
  return Array.isArray(result?.results) ? result.results : null;
}

function indexByProvider(values, expected) {
  if (!Array.isArray(values) || values.length !== expected.length) throw new TypeError("invalid_provider_budget_policy");
  const indexed = new Map();
  for (const value of values) {
    if (!value || typeof value.provider !== "string" || indexed.has(value.provider)) {
      throw new TypeError("invalid_provider_budget_policy");
    }
    indexed.set(value.provider, value);
  }
  if (expected.some((provider) => !indexed.has(provider))) throw new TypeError("invalid_provider_budget_policy");
  return indexed;
}

function paidBudget(provider, row) {
  if (!row || !Number.isSafeInteger(row.per_run_limit_microusd) || row.per_run_limit_microusd < 1 ||
      !(row.monthly_limit_microusd === null ||
        Number.isSafeInteger(row.monthly_limit_microusd) && row.monthly_limit_microusd > 0) ||
      (provider === "modal_cpu" || provider === "modal_gpu") && row.monthly_limit_microusd === null ||
      provider === "runpod_gpu" && row.monthly_limit_microusd !== null) {
    throw new TypeError("invalid_provider_budget_policy");
  }
  return { provider, policy_available: true, scope: "registered_workload_reservation",
    monthly_limit_usd: row.monthly_limit_microusd === null ? null : usdFromMicrousd(row.monthly_limit_microusd),
    per_run_limit_usd: usdFromMicrousd(row.per_run_limit_microusd) };
}

export async function readProviderBudgetPolicy(db) {
  if (!db || typeof db.prepare !== "function") return unavailable();
  try {
    const [boundedResult, modalGpu, freeResult] = await Promise.all([
      db.prepare(`SELECT provider, monthly_limit_microusd, per_run_limit_microusd
        FROM provider_budget_policies`).all(),
      db.prepare(`SELECT monthly_limit_microusd, per_run_limit_microusd, admission_enabled
        FROM modal_gpu_budget_policy WHERE scope='workspace'`).first(),
      db.prepare(`SELECT provider, max_cost_microusd, paid_fallback_allowed
        FROM provider_free_policies`).all(),
    ]);
    const bounded = indexByProvider(rows(boundedResult), ["modal_cpu", "runpod_gpu"]);
    const free = indexByProvider(rows(freeResult), ["kaggle", "huggingface_space"]);
    if (!modalGpu || !Number.isSafeInteger(modalGpu.monthly_limit_microusd) || modalGpu.monthly_limit_microusd < 1 ||
        !Number.isSafeInteger(modalGpu.per_run_limit_microusd) || modalGpu.per_run_limit_microusd < 1 ||
        ![0, 1].includes(modalGpu.admission_enabled)) throw new TypeError("invalid_provider_budget_policy");
    const freeBudgets = ["kaggle", "huggingface_space"].map((provider) => {
      const row = free.get(provider);
      if (!row || row.max_cost_microusd !== 0 || row.paid_fallback_allowed !== 0) {
        throw new TypeError("invalid_provider_budget_policy");
      }
      return { provider, policy_available: true, scope: "registered_free_workload_policy", monthly_limit_usd: "0.00",
        per_run_limit_usd: "0.00", paid_fallback_allowed: false };
    });
    return { schema_version: 1, state: "ready", provider_budgets: [
      paidBudget("modal_cpu", bounded.get("modal_cpu")),
      { ...paidBudget("modal_gpu", modalGpu), admission_enabled: modalGpu.admission_enabled === 1 },
      paidBudget("runpod_gpu", bounded.get("runpod_gpu")),
      ...freeBudgets,
    ] };
  } catch {
    return unavailable();
  }
}
