const RUNPOD_API_ORIGIN = "https://api.runpod.io";
const DEFAULT_TIMEOUT_MS = 12_000;
const MAX_JSON_BYTES = 1024 * 1024;
const POD_ID_RE = /^[A-Za-z0-9_-]{4,128}$/;
const GPU_ID_RE = /^[A-Za-z0-9 ._()+-]{3,128}$/;
const IMAGE_DIGEST_RE = /^[a-z0-9][a-z0-9._/-]{0,199}@sha256:[0-9a-f]{64}$/;

export class RunpodProviderError extends Error {
  constructor(code, status = null, retryAfterSeconds = null) {
    super(code);
    this.name = "RunpodProviderError";
    this.code = code;
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export function runpodConfigured(env) {
  return typeof env?.RUNPOD_API_KEY === "string" && env.RUNPOD_API_KEY.length >= 20 &&
    env.RUNPOD_API_KEY.length <= 512 && !/[\s\x00-\x1f\x7f]/.test(env.RUNPOD_API_KEY) &&
    typeof env?.RUNPOD_WORKLOAD_IMAGE === "string" && IMAGE_DIGEST_RE.test(env.RUNPOD_WORKLOAD_IMAGE) &&
    typeof env?.RUNPOD_GPU_ID === "string" && GPU_ID_RE.test(env.RUNPOD_GPU_ID);
}

function boundedRetryAfter(response) {
  const value = Number(response.headers.get("retry-after"));
  return Number.isSafeInteger(value) && value >= 1 && value <= 300 ? value : null;
}

async function readBoundedJson(response) {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_JSON_BYTES) {
    try { await response.body?.cancel(); } catch {}
    throw new RunpodProviderError("RUNPOD_RESPONSE_TOO_LARGE", response.status);
  }
  if (!response.body) throw new RunpodProviderError("RUNPOD_INVALID_RESPONSE", response.status);
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_JSON_BYTES) {
        try { await reader.cancel(); } catch {}
        throw new RunpodProviderError("RUNPOD_RESPONSE_TOO_LARGE", response.status);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try {
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("shape");
    return value;
  } catch {
    throw new RunpodProviderError("RUNPOD_INVALID_RESPONSE", response.status);
  }
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
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 30_000) {
      throw new RunpodProviderError("RUNPOD_INVALID_TIMEOUT");
    }
    this.apiKey = env.RUNPOD_API_KEY;
    this.image = env.RUNPOD_WORKLOAD_IMAGE;
    this.gpuId = env.RUNPOD_GPU_ID;
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
  }

  async request(path, { method = "GET", body = null, expectedStatus = 200, expectEmpty = false } = {}) {
    if (typeof path !== "string" || !path.startsWith("/v2/") || path.includes("//") || path.includes("..")) {
      throw new RunpodProviderError("RUNPOD_INVALID_PATH");
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response;
    try {
      response = await this.fetchImpl(`${RUNPOD_API_ORIGIN}${path}`, {
        method,
        redirect: "manual",
        headers: {
          authorization: `Bearer ${this.apiKey}`,
          accept: "application/json",
          ...(body === null ? {} : { "content-type": "application/json" }),
        },
        ...(body === null ? {} : { body: JSON.stringify(body) }),
        signal: controller.signal,
      });
    } catch (error) {
      if (error?.name === "AbortError") throw new RunpodProviderError("RUNPOD_PROVIDER_TIMEOUT");
      throw new RunpodProviderError("RUNPOD_NETWORK_ERROR");
    } finally {
      clearTimeout(timeout);
    }
    if (response.status >= 300 && response.status <= 399) {
      try { await response.body?.cancel(); } catch {}
      throw new RunpodProviderError("RUNPOD_REDIRECT_REJECTED", response.status);
    }
    if (response.status !== expectedStatus) {
      try { await response.body?.cancel(); } catch {}
      if (response.ok) throw new RunpodProviderError("RUNPOD_UNEXPECTED_SUCCESS_STATUS", response.status);
      throw new RunpodProviderError(mapHttpError(response.status), response.status, boundedRetryAfter(response));
    }
    if (expectEmpty) {
      try { await response.body?.cancel(); } catch {}
      return null;
    }
    return readBoundedJson(response);
  }

  createPod({ runId, dataCenterId = null }) {
    if (!/^[0-9a-f]{32}$/.test(runId)) throw new RunpodProviderError("RUNPOD_INVALID_RUN_ID");
    if (dataCenterId !== null && !/^[A-Z0-9-]{3,32}$/.test(dataCenterId)) {
      throw new RunpodProviderError("RUNPOD_INVALID_DATACENTER_ID");
    }
    return this.request("/v2/pods", { method: "POST", expectedStatus: 201, body: {
      name: `gpu-control-${runId.slice(0, 12)}`,
      image: this.image,
      gpu: { id: this.gpuId, count: 1 },
      cloud: "SECURE",
      disk: 10,
      entrypoint: ["/opt/gpu-control/idle"],
      cmd: [],
      env: { GPU_CONTROL_RUN_ID: runId },
      ports: [],
      startJupyter: false,
      startSsh: false,
      globalNetworking: false,
      ...(dataCenterId === null ? {} : { dataCenterIds: [dataCenterId] }),
    } });
  }

  getPod(podId) {
    if (!POD_ID_RE.test(podId)) throw new RunpodProviderError("RUNPOD_INVALID_POD_ID");
    return this.request(`/v2/pods/${podId}`);
  }

  listPods() {
    return this.request("/v2/pods");
  }

  async getVerifiedOffer() {
    const value = await this.request("/v2/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE");
    if (!Array.isArray(value.gpus) || value.gpus.length > 1024) {
      throw new RunpodProviderError("RUNPOD_INVALID_CATALOG_RESPONSE");
    }
    const matches = value.gpus.filter((gpu) => gpu?.id === this.gpuId);
    if (matches.length !== 1) throw new RunpodProviderError("RUNPOD_GPU_NOT_IN_CATALOG");
    const gpu = matches[0];
    const price = gpu?.price?.secure;
    if (gpu.secure !== true || typeof price !== "number" || !Number.isFinite(price) || price <= 0 || price > 100 ||
        !Number.isSafeInteger(gpu?.maxCount?.secure) || gpu.maxCount.secure < 1 || gpu.availability !== "HIGH" ||
        !Array.isArray(gpu.dataCenters) || gpu.dataCenters.length < 1 || gpu.dataCenters.length > 1024) {
      throw new RunpodProviderError("RUNPOD_GPU_OFFER_UNAVAILABLE");
    }
    const dataCenters = gpu.dataCenters.filter((item) => item && typeof item.id === "string" &&
      /^[A-Z0-9-]{3,32}$/.test(item.id) && item.availability === "HIGH");
    if (dataCenters.length < 1) throw new RunpodProviderError("RUNPOD_GPU_OFFER_UNAVAILABLE");
    dataCenters.sort((left, right) => left.id.localeCompare(right.id));
    return {
      gpuId: this.gpuId, cloud: "SECURE", gpuCount: 1, hourlyPriceUsd: price,
      availability: "HIGH", dataCenterId: dataCenters[0].id,
      checkedAt: Math.floor(Date.now() / 1000), validForSeconds: 300,
      source: "runpod-rest-v2-catalog",
    };
  }

  runRegisteredWorkload(podId, { planFingerprint, nonce }) {
    if (!POD_ID_RE.test(podId)) throw new RunpodProviderError("RUNPOD_INVALID_POD_ID");
    if (!/^[0-9a-f]{64}$/.test(planFingerprint) || !/^[0-9a-f]{64}$/.test(nonce)) {
      throw new RunpodProviderError("RUNPOD_INVALID_EXECUTION_BINDING");
    }
    return this.request(`/v2/pods/${podId}/exec`, { method: "POST", expectedStatus: 200, body: {
      command: [
        "/opt/gpu-control/run-registered-workload",
        "--plan-fingerprint", planFingerprint,
        "--nonce", nonce,
      ],
      cwd: "/opt/gpu-control",
      timeoutSeconds: 25,
    } });
  }

  async terminatePod(podId) {
    if (!POD_ID_RE.test(podId)) throw new RunpodProviderError("RUNPOD_INVALID_POD_ID");
    return this.request(`/v2/pods/${podId}`, { method: "DELETE", expectedStatus: 204, expectEmpty: true });
  }
}

export function validateCreatedPod(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value) || !POD_ID_RE.test(value.id) ||
      value.name !== expected.name || value.image !== expected.image || value.cloud !== "SECURE" ||
      value.gpu?.id !== expected.gpuId || value.gpu?.count !== 1 || value.globalNetworking?.enabled === true ||
      (Array.isArray(value.ports) && value.ports.length !== 0)) {
    throw new RunpodProviderError("RUNPOD_INVALID_CREATE_RECEIPT");
  }
  return { id: value.id, status: value.status, cost: value.cost, dataCenterId: value.dataCenterId ?? null };
}

export function validateExecResult(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      typeof value.stdout !== "string" || typeof value.stderr !== "string" ||
      value.stdout.length > MAX_JSON_BYTES || value.stderr.length > MAX_JSON_BYTES ||
      !(value.exitCode === null || Number.isSafeInteger(value.exitCode)) ||
      typeof value.timedOut !== "boolean" || typeof value.truncated !== "boolean" ||
      !Number.isSafeInteger(value.durationMs) || value.durationMs < 0) {
    throw new RunpodProviderError("RUNPOD_INVALID_EXEC_RECEIPT");
  }
  if (value.timedOut) throw new RunpodProviderError("RUNPOD_EXEC_WAIT_TIMED_OUT");
  if (value.truncated) throw new RunpodProviderError("RUNPOD_EXEC_OUTPUT_TRUNCATED");
  return value;
}
