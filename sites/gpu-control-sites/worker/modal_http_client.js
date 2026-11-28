import { WORKLOADS } from "./workload_registry.js";
import { MODAL_MAX_RUNTIME_SECONDS } from "./modal_cpu_policy.js";

// Modal control functions cold-started for ~6.3s in production; retain room
// for that startup plus normal request latency while keeping calls bounded.
const MODAL_TIMEOUT_MS = 15000;
const MODAL_API_ORIGIN = "https://unjuno--gpu-control-sites-control-api.us-east.modal.run";
const MODAL_MAX_RESPONSE_BYTES = 8 * 1024;
const WORKLOAD = WORKLOADS.tiny_stories.id;

export function modalConfigured(env) {
  let modalUrl;
  try { modalUrl = new URL(env.MODAL_API_URL); } catch { return false; }
  return modalUrl.origin === MODAL_API_ORIGIN && modalUrl.pathname === "/" &&
    !modalUrl.username && !modalUrl.password && !modalUrl.search && !modalUrl.hash &&
    typeof env.MODAL_PROXY_TOKEN_ID === "string" && /^wk-[A-Za-z0-9_-]{8,}$/.test(env.MODAL_PROXY_TOKEN_ID) &&
    typeof env.MODAL_PROXY_TOKEN_SECRET === "string" && /^ws-[A-Za-z0-9_-]{8,}$/.test(env.MODAL_PROXY_TOKEN_SECRET) &&
    typeof env.MODAL_WORKLOAD_IMAGE_FINGERPRINT === "string" && /^[0-9a-f]{64}$/.test(env.MODAL_WORKLOAD_IMAGE_FINGERPRINT) &&
    !!env.DB && !!env.BUCKET && typeof env.BUCKET.put === "function";
}

export async function modalRequest(env, path, payload, { method = "POST", body = true } = {}) {
  if (!modalConfigured(env)) throw new Error("MODAL_PROVIDER_NOT_CONFIGURED");
  const base = env.MODAL_API_URL.replace(/\/$/, "");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), MODAL_TIMEOUT_MS);
  try {
    const response = await fetch(`${base}${path}`, {
      method,
      redirect: "manual",
      headers: {
        "Authorization": `Bearer ${env.MODAL_PROXY_TOKEN_ID}.${env.MODAL_PROXY_TOKEN_SECRET}`,
        ...(body ? { "content-type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(payload) } : {}),
      signal: controller.signal,
    });
    if (!response.ok) {
      try { await response.body?.cancel(); } catch {}
      if (response.status === 404) throw new Error("MODAL_RUN_NOT_FOUND");
      if ([401, 403, 429].includes(response.status)) throw new Error(`MODAL_PROVIDER_HTTP_${response.status}`);
      if (response.status >= 300 && response.status <= 399) throw new Error("MODAL_PROVIDER_HTTP_3XX");
      if (response.status >= 500 && response.status <= 599) throw new Error("MODAL_PROVIDER_HTTP_5XX");
      throw new Error("MODAL_PROVIDER_REQUEST_FAILED");
    }
    const declaredLength = Number(response.headers.get("content-length"));
    if (Number.isFinite(declaredLength) && declaredLength > MODAL_MAX_RESPONSE_BYTES) {
      try { await response.body?.cancel(); } catch {}
      throw new Error("MODAL_PROVIDER_RESPONSE_TOO_LARGE");
    }
    if (!response.body) throw new Error("MODAL_PROVIDER_INVALID_RESPONSE");
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MODAL_MAX_RESPONSE_BYTES) {
          try { await reader.cancel(); } catch {}
          throw new Error("MODAL_PROVIDER_RESPONSE_TOO_LARGE");
        }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("MODAL_PROVIDER_INVALID_RESPONSE");
    return value;
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("MODAL_PROVIDER_TIMEOUT");
    throw error;
  } finally { clearTimeout(timeout); }
}

export function modalPayload(plan, env) {
  return {
    workload: plan.workload,
    repository: plan.repository,
    source_sha: plan.source_sha,
    registered_image_digest: plan.image_digest,
    image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT,
    plan_fingerprint: plan.fingerprint,
    parameters: JSON.parse(plan.parameters_json),
    runtime_seconds: plan.runtime_seconds,
  };
}

export async function providerHealth(env) {
  if (!modalConfigured(env)) return { provider: null, checks: { configured: false } };
  try {
    const value = await modalRequest(env, "/v1/health", null, { method: "GET", body: false });
    const checks = {
      configured: true,
      ready: value.ready === true,
      provider: value.provider === "modal_cpu",
      workload: value.workload === WORKLOAD,
      registered_image_digest: value.registered_image_digest === env.CPU_WORKLOAD_IMAGE_DIGEST,
      image_fingerprint: value.image_fingerprint === env.MODAL_WORKLOAD_IMAGE_FINGERPRINT,
      max_runtime_seconds: value.max_runtime_seconds === MODAL_MAX_RUNTIME_SECONDS,
      source_sha: value.source_sha === env.CPU_WORKLOAD_SOURCE_SHA,
    };
    return { provider: Object.values(checks).every(Boolean) ? value : null, checks };
  } catch (error) {
    const allowedErrorCodes = new Set([
      "MODAL_PROVIDER_HTTP_401", "MODAL_PROVIDER_HTTP_403", "MODAL_PROVIDER_HTTP_429",
      "MODAL_PROVIDER_HTTP_3XX", "MODAL_PROVIDER_HTTP_5XX", "MODAL_PROVIDER_REQUEST_FAILED",
      "MODAL_PROVIDER_RESPONSE_TOO_LARGE", "MODAL_PROVIDER_INVALID_RESPONSE", "MODAL_PROVIDER_TIMEOUT",
    ]);
    const errorCode = allowedErrorCodes.has(error?.message) ? error.message : "MODAL_PROVIDER_NETWORK_ERROR";
    return { provider: null, checks: { configured: true, request_succeeded: false, error_code: errorCode } };
  }
}
