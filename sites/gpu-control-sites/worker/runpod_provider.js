const RUNPOD_JOB_ORIGIN = "https://api.runpod.ai";
const PROVIDER_ADAPTER_ORIGIN = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
const RUNPOD_RELAY_PATH = "/internal/runpod/v1/proxy";
const RUNPOD_MANAGEMENT_ORIGIN = "https://api.runpod.io";
// RunPod's queue API can take longer than a typical control-plane request to
// acknowledge a cold endpoint. Keep the client timeout aligned with the
// registered workload's hard 30-second execution limit; ambiguous outcomes
// still remain non-retriable and are reconciled through the provider TTL.
const DEFAULT_TIMEOUT_MS = 30_000;
const MAX_JSON_BYTES = 1024 * 1024;
const JOB_ID_RE = /^[A-Za-z0-9_-]{4,128}$/;
const ENDPOINT_ID_RE = /^[A-Za-z0-9_-]{4,128}$/;
const IMAGE_DIGEST_RE = /^[a-z0-9][a-z0-9._/-]{0,199}@sha256:[0-9a-f]{64}$/;

export class RunpodProviderError extends Error {
  constructor(code, status = null, retryAfterSeconds = null) {
    super(code); this.name = "RunpodProviderError"; this.code = code;
    this.status = status; this.retryAfterSeconds = retryAfterSeconds;
  }
}

export function runpodConfigured(env) {
  const directKey = typeof env?.RUNPOD_API_KEY === "string" && env.RUNPOD_API_KEY.length >= 20 && env.RUNPOD_API_KEY.length <= 512 &&
    !/[\s\x00-\x1f\x7f]/.test(env.RUNPOD_API_KEY);
  const relay = env?.RUNPOD_USE_PROVIDER_ADAPTER === "true" &&
    typeof env?.PROVIDER_ADAPTER_URL === "string" && typeof env?.PROVIDER_ADAPTER_PROXY_TOKEN_ID === "string" &&
    typeof env?.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET === "string";
  return (directKey || relay) && typeof env?.RUNPOD_WORKLOAD_IMAGE === "string" &&
    IMAGE_DIGEST_RE.test(env.RUNPOD_WORKLOAD_IMAGE) && typeof env?.RUNPOD_SERVERLESS_ENDPOINT_ID === "string" &&
    ENDPOINT_ID_RE.test(env.RUNPOD_SERVERLESS_ENDPOINT_ID) && typeof env?.RUNPOD_GPU_ID === "string" &&
    /^[A-Za-z0-9 ._()+-]{3,128}$/.test(env.RUNPOD_GPU_ID) && typeof env?.RUNPOD_SERVERLESS_HOURLY_PRICE_USD === "string" &&
    /^(?:0|[1-9][0-9]?)\.[0-9]{6}$/.test(env.RUNPOD_SERVERLESS_HOURLY_PRICE_USD) && Number(env.RUNPOD_SERVERLESS_HOURLY_PRICE_USD) > 0 &&
    typeof env?.RUNPOD_SERVERLESS_GPU_POOL_ID === "string" && /^[A-Z0-9_]{3,64}$/.test(env.RUNPOD_SERVERLESS_GPU_POOL_ID) &&
    typeof env?.RUNPOD_WORKLOAD_SOURCE_SHA === "string" && /^[0-9a-f]{40}$/.test(env.RUNPOD_WORKLOAD_SOURCE_SHA);
}

function jobTransport(env) {
  if (env?.RUNPOD_USE_PROVIDER_ADAPTER !== "true") return { origin: RUNPOD_JOB_ORIGIN, headers: {}, relay: false };
  if (typeof env?.PROVIDER_ADAPTER_URL !== "string" ||
      typeof env?.PROVIDER_ADAPTER_PROXY_TOKEN_ID !== "string" || !env.PROVIDER_ADAPTER_PROXY_TOKEN_ID ||
      typeof env?.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET !== "string" || !env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET)
    throw new RunpodProviderError("RUNPOD_RELAY_NOT_CONFIGURED");
  let relay; let adapter;
  try { adapter = new URL(env.PROVIDER_ADAPTER_URL); relay = new URL(RUNPOD_RELAY_PATH, `${adapter.origin}/`); }
  catch { throw new RunpodProviderError("RUNPOD_RELAY_INVALID"); }
  if (adapter.origin !== PROVIDER_ADAPTER_ORIGIN || adapter.pathname !== "/" || adapter.search || adapter.hash || adapter.username || adapter.password ||
      relay.protocol !== "https:" || relay.origin !== adapter.origin || relay.pathname !== RUNPOD_RELAY_PATH ||
      relay.search || relay.hash || relay.username || relay.password)
    throw new RunpodProviderError("RUNPOD_RELAY_INVALID");
  return { origin: relay.href.replace(/\/$/, ""), relay: true, headers: {
    authorization: `Bearer ${env.PROVIDER_ADAPTER_PROXY_TOKEN_ID}.${env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET}`,
  } };
}

function boundedRetryAfter(response) {
  const value = Number(response.headers.get("retry-after"));
  return Number.isSafeInteger(value) && value >= 1 && value <= 300 ? value : null;
}
async function readBoundedJson(response, signal = null) {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_JSON_BYTES) throw new RunpodProviderError("RUNPOD_RESPONSE_TOO_LARGE", response.status);
  if (!response.body) throw new RunpodProviderError("RUNPOD_INVALID_RESPONSE", response.status);
  const reader = response.body.getReader(); const chunks = []; let size = 0;
  try {
    for (;;) {
      let onAbort;
      const read = reader.read();
      const next = signal === null ? read : Promise.race([read, new Promise((_, reject) => {
        onAbort = () => reject(new DOMException("The operation was aborted", "AbortError"));
        if (signal.aborted) onAbort(); else signal.addEventListener("abort", onAbort, { once: true });
      })]);
      let chunk;
      try { chunk = await next; } finally { if (onAbort) signal.removeEventListener("abort", onAbort); }
      const { done, value } = chunk; if (done) break; size += value.byteLength;
      if (size > MAX_JSON_BYTES) { await reader.cancel(); throw new RunpodProviderError("RUNPOD_RESPONSE_TOO_LARGE", response.status); }
      chunks.push(value); }
  } catch (error) {
    if (error?.name === "AbortError") { try { await reader.cancel(); } catch {} }
    throw error;
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("shape"); return value;
  } catch { throw new RunpodProviderError("RUNPOD_INVALID_RESPONSE", response.status); }
}
function mapHttpError(status) {
  if (status === 400 || status === 422) return "RUNPOD_REQUEST_REJECTED";
  if (status === 401) return "RUNPOD_AUTHENTICATION_FAILED";
  if (status === 402) return "RUNPOD_INSUFFICIENT_BALANCE";
  if (status === 403) return "RUNPOD_PERMISSION_DENIED";
  if (status === 404) return "RUNPOD_NOT_FOUND";
  if (status === 409) return "RUNPOD_NOT_READY";
  if (status === 429) return "RUNPOD_RATE_LIMITED";
  if (status >= 500) return "RUNPOD_PROVIDER_UNAVAILABLE";
  return "RUNPOD_REQUEST_FAILED";
}

export class RunpodV2Client {
  constructor(env, { fetchImpl = fetch, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
    if (!runpodConfigured(env)) throw new RunpodProviderError("RUNPOD_PROVIDER_NOT_CONFIGURED");
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000) throw new RunpodProviderError("RUNPOD_INVALID_TIMEOUT");
    this.apiKey = env.RUNPOD_API_KEY || ""; this.image = env.RUNPOD_WORKLOAD_IMAGE; this.gpuId = env.RUNPOD_GPU_ID;
    this.endpointId = env.RUNPOD_SERVERLESS_ENDPOINT_ID;
    // This configuration value is a fail-closed maximum, not current price
    // evidence. Current Serverless list price comes from REST v2 Catalog.
    this.maximumHourlyPriceUsd = Number(env.RUNPOD_SERVERLESS_HOURLY_PRICE_USD);
    this.gpuPoolId = env.RUNPOD_SERVERLESS_GPU_POOL_ID; this.sourceSha = env.RUNPOD_WORKLOAD_SOURCE_SHA;
    const transport = jobTransport(env); this.jobOrigin = transport.origin; this.jobHeaders = transport.headers; this.jobRelay = transport.relay;
    this.fetchImpl = fetchImpl; this.timeoutMs = timeoutMs;
  }
  async request(path, { method = "GET", body = null, expectedStatus = 200 } = {}) {
    if (typeof path !== "string" || !path.startsWith(`/v2/${this.endpointId}/`) || path.includes("..") || path.includes("//"))
      throw new RunpodProviderError("RUNPOD_INVALID_PATH");
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), this.timeoutMs); let response;
    const relayBody = this.jobRelay ? { method, path, body } : null;
    try { response = await this.fetchImpl(this.jobRelay ? this.jobOrigin : `${this.jobOrigin}${path}`, {
      method: this.jobRelay ? "POST" : method, redirect: "manual",
      headers: { ...(this.jobRelay ? {} : { authorization: `Bearer ${this.apiKey}` }), accept: "application/json", ...this.jobHeaders,
        ...((body === null && !this.jobRelay) ? {} : { "content-type": "application/json" }) },
      ...((body === null && !this.jobRelay) ? {} : { body: JSON.stringify(this.jobRelay ? relayBody : body) }), signal: controller.signal });
      if (response.status >= 300 && response.status <= 399) { await response.body?.cancel(); throw new RunpodProviderError("RUNPOD_REDIRECT_REJECTED", response.status); }
      if (response.status !== expectedStatus) { await response.body?.cancel();
        if (response.ok) throw new RunpodProviderError("RUNPOD_UNEXPECTED_SUCCESS_STATUS", response.status);
        throw new RunpodProviderError(mapHttpError(response.status), response.status, boundedRetryAfter(response)); }
      return await readBoundedJson(response, controller.signal);
    } catch (error) { if (error?.name === "AbortError") throw new RunpodProviderError("RUNPOD_PROVIDER_TIMEOUT");
      if (error instanceof RunpodProviderError) throw error; throw new RunpodProviderError("RUNPOD_NETWORK_ERROR"); }
    finally { clearTimeout(timeout); }
  }
  async managementRequest(path) {
    if (typeof path !== "string" || !path.startsWith("/v2/") || path.includes("..") || path.includes("//"))
      throw new RunpodProviderError("RUNPOD_INVALID_PATH");
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), this.timeoutMs); let response;
    try { response = await this.fetchImpl(`${RUNPOD_MANAGEMENT_ORIGIN}${path}`, { method: "GET", redirect: "manual",
      headers: { authorization: `Bearer ${this.apiKey}`, accept: "application/json" }, signal: controller.signal });
      if (response.status >= 300 && response.status <= 399) { await response.body?.cancel(); throw new RunpodProviderError("RUNPOD_REDIRECT_REJECTED", response.status); }
      if (response.status !== 200) { await response.body?.cancel(); throw new RunpodProviderError(mapHttpError(response.status), response.status, boundedRetryAfter(response)); }
      return await readBoundedJson(response, controller.signal);
    } catch (error) { if (error?.name === "AbortError") throw new RunpodProviderError("RUNPOD_PROVIDER_TIMEOUT");
      if (error instanceof RunpodProviderError) throw error; throw new RunpodProviderError("RUNPOD_NETWORK_ERROR"); }
    finally { clearTimeout(timeout); }
  }
  getEndpoint() { return this.managementRequest(`/v2/serverless/${this.endpointId}`); }
  getGpuCatalog() { return this.managementRequest("/v2/catalog/gpus"); }
  async getVerifiedOffer() {
    const endpoint = await this.getEndpoint();
    const noMounts = Array.isArray(endpoint.networkVolumes) && endpoint.networkVolumes.length === 0 &&
      Array.isArray(endpoint.mounts?.network) && endpoint.mounts.network.length === 0 &&
      Array.isArray(endpoint.mounts?.global) && endpoint.mounts.global.length === 0;
    if (endpoint.id !== this.endpointId || endpoint.type !== "QUEUE" || endpoint.image !== this.image ||
        endpoint.gpu?.count !== 1 || !Array.isArray(endpoint.gpu?.pools) || endpoint.gpu.pools.length !== 1 ||
        endpoint.gpu.pools[0] !== this.gpuPoolId || endpoint.workers?.min !== 0 || endpoint.workers?.max !== 1 ||
        endpoint.workers?.idleTimeout !== 5 ||
        !Number.isSafeInteger(endpoint.timeout) || endpoint.timeout < 5000 || endpoint.timeout > 30_000 ||
        !Array.isArray(endpoint.ports) || endpoint.ports.length !== 0 || !noMounts || !["", null, undefined].includes(endpoint.args) ||
        endpoint.env?.GPU_CONTROL_SOURCE_SHA !== this.sourceSha ||
        endpoint.env?.GPU_CONTROL_IMAGE_DIGEST !== this.image.slice(this.image.indexOf("@") + 1)) {
      throw new RunpodProviderError("RUNPOD_ENDPOINT_CONFIGURATION_MISMATCH");
    }
    const catalog = await this.getGpuCatalog();
    const matches = Array.isArray(catalog.gpus) ? catalog.gpus.filter((gpu) => gpu?.id === this.gpuId) : [];
    const gpu = matches.length === 1 ? matches[0] : null;
    const hourlyPriceUsd = gpu?.price?.serverless;
    if (!gpu || gpu.pool !== this.gpuPoolId || typeof hourlyPriceUsd !== "number" || !Number.isFinite(hourlyPriceUsd) ||
        hourlyPriceUsd <= 0 || hourlyPriceUsd > this.maximumHourlyPriceUsd) {
      throw new RunpodProviderError("RUNPOD_CATALOG_PRICE_INVALID_OR_ABOVE_MAXIMUM");
    }
    return { gpuId: this.gpuId, cloud: "SERVERLESS", gpuCount: 1, hourlyPriceUsd,
      availability: "CONFIGURED", dataCenterId: this.endpointId, checkedAt: Math.floor(Date.now() / 1000),
      validForSeconds: 300, source: "runpod-rest-v2-catalog" };
  }
  submitJob({ runId, planFingerprint, nonce, completionKeyB64, completionKeyId, sourceSha }) {
    if (!/^[0-9a-f]{32}$/.test(runId) || !/^[0-9a-f]{64}$/.test(planFingerprint) || !/^[0-9a-f]{64}$/.test(nonce) ||
        !/^(?:[A-Za-z0-9+/]{43}=)$/.test(completionKeyB64) || !/^[0-9a-f]{32}$/.test(completionKeyId) || !/^[0-9a-f]{40}$/.test(sourceSha))
      throw new RunpodProviderError("RUNPOD_INVALID_EXECUTION_BINDING");
    return this.request(`/v2/${this.endpointId}/run`, { method: "POST", body: { input: { schema_version: 1, run_id: runId,
      plan_fingerprint: planFingerprint, nonce, completion_key_b64: completionKeyB64, completion_key_id: completionKeyId,
      source_sha: sourceSha, image_digest: this.image.slice(this.image.indexOf("@") + 1), execution_name: `gpu-control-${runId.slice(0, 12)}` },
      policy: { executionTimeout: 30_000, ttl: 300_000 } } });
  }
  getJob(jobId) { if (!JOB_ID_RE.test(jobId)) throw new RunpodProviderError("RUNPOD_INVALID_JOB_ID"); return this.request(`/v2/${this.endpointId}/status/${jobId}`); }
  async cancelJob(jobId) {
    if (!JOB_ID_RE.test(jobId)) throw new RunpodProviderError("RUNPOD_INVALID_JOB_ID");
    const value = validateJobStatus(await this.request(`/v2/${this.endpointId}/cancel/${jobId}`, { method: "POST" }), jobId);
    if (value.status !== "CANCELLED") throw new RunpodProviderError("RUNPOD_CANCELLATION_NOT_TERMINAL");
    return value;
  }
}

export function validateSubmittedJob(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) || !JOB_ID_RE.test(value.id || "") ||
      !["IN_QUEUE", "IN_PROGRESS"].includes(value.status)) throw new RunpodProviderError("RUNPOD_INVALID_SUBMISSION_RECEIPT");
  return { id: value.id, status: value.status };
}
export function validateJobStatus(value, expectedId) {
  if (!value || typeof value !== "object" || Array.isArray(value) || value.id !== expectedId ||
      !["IN_QUEUE", "IN_PROGRESS", "COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"].includes(value.status))
    throw new RunpodProviderError("RUNPOD_INVALID_JOB_STATUS");
  return value;
}
