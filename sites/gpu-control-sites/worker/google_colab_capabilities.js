const SUBSCRIPTION_TIERS = new Set([
  "SUBSCRIPTION_TIER_FREE", "SUBSCRIPTION_TIER_PRO", "SUBSCRIPTION_TIER_PRO_PLUS",
]);
const RUNTIME_VARIANTS = new Set(["VARIANT_CPU", "VARIANT_GPU", "VARIANT_TPU"]);
const RUNTIME_SHAPES = new Set(["SHAPE_STANDARD", "SHAPE_HIGHMEM"]);

function validRuntimeKey(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    RUNTIME_VARIANTS.has(value.variant) &&
    typeof value.accelerator === "string" && /^[A-Za-z0-9._-]{1,32}$/.test(value.accelerator) &&
    RUNTIME_SHAPES.has(value.shape);
}

/** Validate provider payloads and project only the capability facts Sites uses. */
export function projectGoogleColabCapabilities(subscription, specData, runtimeData) {
  const runtimeSpecs = specData?.runtimeSpecs;
  const runtimes = runtimeData?.runtimes;
  if (!subscription || typeof subscription !== "object" || Array.isArray(subscription) ||
      !SUBSCRIPTION_TIERS.has(subscription.tier) ||
      !Array.isArray(runtimeSpecs) || runtimeSpecs.length > 200 ||
      !Array.isArray(runtimes) || runtimes.length > 1_000 ||
      runtimeSpecs.some((item) => !item || typeof item !== "object" || Array.isArray(item) ||
        !validRuntimeKey(item.key) || typeof item.eligible !== "boolean") ||
      runtimes.some((runtime) => !runtime || typeof runtime !== "object" || Array.isArray(runtime) ||
        typeof runtime.name !== "string" || !/^runtimes\/[A-Za-z0-9-]{1,128}$/.test(runtime.name) ||
        !validRuntimeKey(runtime.runtimeSpec?.key))) {
    throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
  }
  const eligibleGpuSpecs = runtimeSpecs
    .filter((item) => item.key.variant === "VARIANT_GPU")
    .map((item) => ({ accelerator: item.key.accelerator, shape: item.key.shape, eligible: item.eligible }))
    .slice(0, 100);
  const activeGpuRuntimeCount = runtimes.filter((runtime) =>
    runtime.runtimeSpec.key.variant === "VARIANT_GPU").length;
  return { tier: subscription.tier, activeRuntimeCount: runtimes.length,
    activeGpuRuntimeCount, eligibleGpuSpecs };
}
