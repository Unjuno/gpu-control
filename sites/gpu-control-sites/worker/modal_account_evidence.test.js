import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { canonicalJson } from "./canonical_json.js";

function evidence(overrides = {}) {
  const body = { schema_version: 1, workspace: "unjuno", environment: "main",
    usage_limit_usd: "1.00", credits_used_usd: "0.15", charges_usd: "0.00", gpu: "L4",
    hourly_price_usd: "0.400000", price_source: "https://modal.com/pricing",
    verified_at: 900, expires_at: 1800, ...overrides };
  return { ...body, evidence_id: createHash("sha256").update(canonicalJson(body)).digest("hex") };
}

test("L4 evidence binds a fresh one-dollar workspace cap, observed usage, and exact quote", async () => {
  const value = evidence();
  assert.deepEqual(await readModalGpuAccountEvidence({ MAP_TRAINING_ACCOUNT_EVIDENCE_JSON: JSON.stringify(value) }, {
    key: "MAP_TRAINING_ACCOUNT_EVIDENCE_JSON", gpu: "L4", usageLimitUsd: "1.00",
    expectedHourlyMicrousd: 400_000, requiredHeadroomMicrousd: 260_000, now: 1_000,
  }), value);
});

test("L4 account evidence rejects stale, over-budget, wrong-cap, and wrong-price observations", async () => {
  const check = (value, options = {}) => readModalGpuAccountEvidence({
    MAP_TRAINING_ACCOUNT_EVIDENCE_JSON: JSON.stringify(value),
  }, { key: "MAP_TRAINING_ACCOUNT_EVIDENCE_JSON", gpu: "L4", usageLimitUsd: "1.00",
    expectedHourlyMicrousd: 400_000, requiredHeadroomMicrousd: 260_000, now: 1_000, ...options });
  assert.equal(await check(evidence({ expires_at: 999 })), null);
  assert.equal(await check(evidence({ credits_used_usd: "0.80" })), null);
  assert.equal(await check(evidence({ usage_limit_usd: "30.00" })), null);
  assert.equal(await check(evidence({ hourly_price_usd: "0.500000" })), null);
  assert.equal(await check(evidence({ gpu: "T4" })), null);
});
