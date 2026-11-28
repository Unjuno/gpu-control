import test from "node:test";
import assert from "node:assert/strict";
import { projectGoogleColabCapabilities } from "./google_colab_capabilities.js";

const gpuKey = { variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD" };
const cpuKey = { variant: "VARIANT_CPU", accelerator: "CPU", shape: "SHAPE_STANDARD" };

test("projects bounded, safe Colab capability facts", () => {
  const result = projectGoogleColabCapabilities(
    { tier: "SUBSCRIPTION_TIER_FREE", private: "must not escape" },
    { runtimeSpecs: [{ key: gpuKey, eligible: true }, { key: cpuKey, eligible: true, token: "secret" }] },
    { runtimes: [{ name: "runtimes/abc-123", runtimeSpec: { key: gpuKey }, proxyToken: "secret" }] },
  );
  assert.deepEqual(result, { tier: "SUBSCRIPTION_TIER_FREE", activeRuntimeCount: 1,
    activeGpuRuntimeCount: 1, eligibleGpuSpecs: [{ accelerator: "T4", shape: "SHAPE_STANDARD", eligible: true }] });
});

test("rejects malformed or unrecognized provider capability responses", () => {
  const validSpecs = { runtimeSpecs: [{ key: gpuKey, eligible: true }] };
  const validRuntimes = { runtimes: [] };
  for (const [subscription, specs, runtimes] of [
    [{ tier: "UNKNOWN" }, validSpecs, validRuntimes],
    [{ tier: "SUBSCRIPTION_TIER_FREE" }, { runtimeSpecs: [{ key: { ...gpuKey, accelerator: "T4!" }, eligible: true }] }, validRuntimes],
    [{ tier: "SUBSCRIPTION_TIER_FREE" }, validSpecs, { runtimes: [{ name: "../other", runtimeSpec: { key: gpuKey } }] }],
    [{ tier: "SUBSCRIPTION_TIER_FREE" }, { runtimeSpecs: new Array(201).fill({ key: gpuKey, eligible: true }) }, validRuntimes],
  ]) assert.throws(() => projectGoogleColabCapabilities(subscription, specs, runtimes),
    { message: "GOOGLE_COLAB_RESPONSE_INVALID" });
});
