import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { canonicalJson } from "./canonical_json.js";
import { modalGpuWorkloadAdmissionEnabled, readModalGpuProviderEvidence } from "./modal_gpu_policy.js";

test("Modal GPU admission accepts only the literal enabled value", () => {
  assert.equal(modalGpuWorkloadAdmissionEnabled({ MODAL_GPU_WORKLOAD_ADMISSION_ENABLED: "true" }), true);
  for (const value of [undefined, null, "", "TRUE", "1", "yes", true]) {
    assert.equal(modalGpuWorkloadAdmissionEnabled({ MODAL_GPU_WORKLOAD_ADMISSION_ENABLED: value }), false);
  }
  assert.equal(modalGpuWorkloadAdmissionEnabled({}), false);
});

test("Modal GPU provider evidence policy binds the fixed T4 and workspace cap", async () => {
  const body = { schema_version: 1, workspace: "unjuno", environment: "main",
    usage_limit_usd: "30.00", credits_used_usd: "0.15", charges_usd: "0.00",
    gpu: "T4", hourly_price_usd: "0.000164", price_source: "https://modal.com/pricing",
    verified_at: 900, expires_at: 1200 };
  const evidence = { ...body,
    evidence_id: createHash("sha256").update(canonicalJson(body)).digest("hex") };
  const env = { MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify(evidence) };
  assert.deepEqual(await readModalGpuProviderEvidence(env, 1000), evidence);
  assert.equal(await readModalGpuProviderEvidence(env, 1201), null);
  const wrongGpu = { ...body, gpu: "L4" };
  wrongGpu.evidence_id = createHash("sha256").update(canonicalJson(wrongGpu)).digest("hex");
  assert.equal(await readModalGpuProviderEvidence({
    MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify(wrongGpu),
  }, 1000), null);
  const wrongCap = { ...body, usage_limit_usd: "31.00" };
  wrongCap.evidence_id = createHash("sha256").update(canonicalJson(wrongCap)).digest("hex");
  assert.equal(await readModalGpuProviderEvidence({
    MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify(wrongCap),
  }, 1000), null);
});
