const PROVIDERS = Object.freeze([
  "modal", "runpod_gpu", "kaggle", "huggingface_space",
]);
const MODAL_COMPUTE_RESERVATION_SOURCES = new Set([
  "modal_cpu", "modal_gpu_canary", "map_training", "owner_selected_training",
]);

export function usdFromMicrousd(value) {
  if (!Number.isSafeInteger(value) || value < 0) throw new TypeError("invalid_provider_budget_policy");
  const amount = BigInt(value);
  const whole = amount / 1_000_000n;
  const fractional = (amount % 1_000_000n).toString().padStart(6, "0").replace(/0+$/, "");
  return `${whole}.${fractional ? fractional.padEnd(2, "0") : "00"}`;
}

export function utcMonthKey(epochSeconds) {
  if (!Number.isSafeInteger(epochSeconds) || epochSeconds < 0) throw new TypeError("invalid_budget_period");
  const date = new Date(epochSeconds * 1000);
  return `${date.getUTCFullYear().toString().padStart(4, "0")}-${(date.getUTCMonth() + 1).toString().padStart(2, "0")}`;
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
      provider === "runpod_gpu" && row.monthly_limit_microusd !== null) {
    throw new TypeError("invalid_provider_budget_policy");
  }
  if (provider === "modal" && (row.monthly_limit_microusd !== 30_000_000 ||
      row.per_run_limit_microusd !== 1_000_000) ||
      provider === "runpod_gpu" && row.per_run_limit_microusd !== 1_000_000) {
    throw new TypeError("invalid_provider_budget_policy");
  }
  return { provider, policy_available: true,
    scope: provider === "modal" ? "modal_compute_shared_across_routes" : "provider_reservation",
    monthly_limit_usd: row.monthly_limit_microusd === null ? null : usdFromMicrousd(row.monthly_limit_microusd),
    per_run_limit_usd: usdFromMicrousd(row.per_run_limit_microusd),
    monthly_limit_microusd: row.monthly_limit_microusd,
    per_run_limit_microusd: row.per_run_limit_microusd,
    ...(provider === "modal" ? {
      monthly_reserved_microusd: row.monthly_reserved_microusd,
      monthly_reserved_usd: usdFromMicrousd(row.monthly_reserved_microusd),
      monthly_remaining_microusd: Math.max(0, row.monthly_limit_microusd - row.monthly_reserved_microusd),
      monthly_remaining_usd: usdFromMicrousd(Math.max(0, row.monthly_limit_microusd - row.monthly_reserved_microusd)),
    } : {}) };
}

export async function readProviderBudgetPolicy(db) {
  if (!db || typeof db.prepare !== "function") return unavailable();
  try {
    const currentPeriod = utcMonthKey(Math.floor(Date.now() / 1000));
    const [runpod, modal, modalUsage, modalGpuAdmission, freeResult] = await Promise.all([
      db.prepare(`SELECT provider, monthly_limit_microusd, per_run_limit_microusd
        FROM provider_budget_policies WHERE provider='runpod_gpu'`).first(),
      db.prepare(`SELECT monthly_limit_microusd, per_run_limit_microusd
        FROM modal_compute_budget_policy WHERE scope='workspace'`).first(),
      db.prepare(`SELECT COALESCE(SUM(reserved_microusd), 0) AS monthly_reserved_microusd
        FROM modal_compute_budget_reservations WHERE period_key=?`).bind(currentPeriod).first(),
      db.prepare(`SELECT admission_enabled FROM modal_gpu_admission_policy WHERE scope='workspace'`).first(),
      db.prepare(`SELECT provider, max_cost_microusd, paid_fallback_allowed
        FROM provider_free_policies`).all(),
    ]);
    const free = indexByProvider(rows(freeResult), ["kaggle", "huggingface_space"]);
    if (!modalGpuAdmission || ![0, 1].includes(modalGpuAdmission.admission_enabled) ||
        !modalUsage || !Number.isSafeInteger(modalUsage.monthly_reserved_microusd) || modalUsage.monthly_reserved_microusd < 0) {
      throw new TypeError("invalid_provider_budget_policy");
    }
    const freeBudgets = ["kaggle", "huggingface_space"].map((provider) => {
      const row = free.get(provider);
      if (!row || row.max_cost_microusd !== 0 || row.paid_fallback_allowed !== 0) {
        throw new TypeError("invalid_provider_budget_policy");
      }
      return { provider, policy_available: true, scope: "registered_free_workload_policy", monthly_limit_usd: "0.00",
        per_run_limit_usd: "0.00", paid_fallback_allowed: false };
    });
    return { schema_version: 1, state: "ready", provider_budgets: [
      { ...paidBudget("modal", { ...modal, monthly_reserved_microusd: modalUsage.monthly_reserved_microusd }), routes: ["modal_cpu", "modal_gpu"],
        modal_gpu_admission_enabled: modalGpuAdmission.admission_enabled === 1 },
      paidBudget("runpod_gpu", runpod),
      ...freeBudgets,
    ] };
  } catch {
    return unavailable();
  }
}

export function prepareModalComputeBudgetReservation(db, {
  runId, source, fingerprint, periodKey, requestedMicrousd, now, requireGpuAdmission = false,
}) {
  if (!db || typeof db.prepare !== "function" || !/^[0-9a-f]{32}$/.test(runId || "") ||
      !MODAL_COMPUTE_RESERVATION_SOURCES.has(source) || !/^[0-9a-f]{64}$/.test(fingerprint || "") ||
      !/^\d{4}-\d{2}$/.test(periodKey || "") || !Number.isSafeInteger(requestedMicrousd) ||
      requestedMicrousd < 1 || !Number.isSafeInteger(now) || now < 0) {
    throw new TypeError("invalid_modal_compute_budget_reservation");
  }
  const gpuAdmissionClause = requireGpuAdmission
    ? `AND EXISTS (SELECT 1 FROM modal_gpu_admission_policy a
        WHERE a.scope='workspace' AND a.admission_enabled=1)` : "";
  return db.prepare(`INSERT OR IGNORE INTO modal_compute_budget_reservations
      (run_id, source, plan_fingerprint, period_key, reserved_microusd, created_at)
    SELECT ?, ?, ?, ?, ?, ? FROM modal_compute_budget_policy p
    WHERE p.scope='workspace' AND ?<=p.per_run_limit_microusd
      AND COALESCE((SELECT SUM(r.reserved_microusd) FROM modal_compute_budget_reservations r
        WHERE r.period_key=?), 0) + ? <= p.monthly_limit_microusd
      ${gpuAdmissionClause}`)
    .bind(runId, source, fingerprint, periodKey, requestedMicrousd, now,
      requestedMicrousd, periodKey, requestedMicrousd);
}
