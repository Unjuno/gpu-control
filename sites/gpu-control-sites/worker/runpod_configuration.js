import { providerAdapterConfigured } from "./provider_adapter_client.js";

const ENDPOINT_ID_RE = /^[A-Za-z0-9_-]{4,128}$/;
const IMAGE_DIGEST_RE = /^[a-z0-9][a-z0-9._/-]{0,199}@sha256:[0-9a-f]{64}$/;
const GPU_ID_RE = /^[A-Za-z0-9 ._()+-]{3,128}$/;
const PRICE_RE = /^(?:0|[1-9][0-9]?)\.[0-9]{6}$/;
const GPU_POOL_RE = /^[A-Z0-9_]{3,64}$/;
const SOURCE_SHA_RE = /^[0-9a-f]{40}$/;

function validApiKey(value) {
  return typeof value === "string" && value.length >= 20 && value.length <= 512 &&
    !/[\s\x00-\x1f\x7f]/.test(value);
}

/** Parse and validate the operator-pinned RunPod profile without returning secrets. */
export function readRunpodConfiguration(env) {
  if (!env || typeof env !== "object") return null;
  const directKey = validApiKey(env.RUNPOD_API_KEY);
  const relay = env.RUNPOD_USE_PROVIDER_ADAPTER === "true" && providerAdapterConfigured(env);
  const image = env.RUNPOD_WORKLOAD_IMAGE;
  const endpointId = env.RUNPOD_SERVERLESS_ENDPOINT_ID;
  const gpuId = env.RUNPOD_GPU_ID;
  const hourlyPriceUsd = env.RUNPOD_SERVERLESS_HOURLY_PRICE_USD;
  const gpuPoolId = env.RUNPOD_SERVERLESS_GPU_POOL_ID;
  const sourceSha = env.RUNPOD_WORKLOAD_SOURCE_SHA;

  if (!(directKey || relay) || typeof image !== "string" || !IMAGE_DIGEST_RE.test(image) ||
      typeof endpointId !== "string" || !ENDPOINT_ID_RE.test(endpointId) ||
      typeof gpuId !== "string" || !GPU_ID_RE.test(gpuId) ||
      typeof hourlyPriceUsd !== "string" || !PRICE_RE.test(hourlyPriceUsd) || Number(hourlyPriceUsd) <= 0 ||
      typeof gpuPoolId !== "string" || !GPU_POOL_RE.test(gpuPoolId) ||
      typeof sourceSha !== "string" || !SOURCE_SHA_RE.test(sourceSha)) return null;

  return Object.freeze({ image, endpointId, gpuId, maximumHourlyPriceUsd: Number(hourlyPriceUsd),
    hourlyPriceUsd, gpuPoolId, sourceSha, relay });
}

/** Return the direct credential only to the provider transport owner. */
export function readRunpodApiKey(env) {
  return validApiKey(env?.RUNPOD_API_KEY) ? env.RUNPOD_API_KEY : "";
}
