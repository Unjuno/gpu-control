import { canonicalJson } from "./canonical_json.js";
import { readBoundedResponseBytes } from "./http_response_body.js";

const DELEGATION_TTL_SECONDS = 60;
// The authenticated Modal adapter can cold-start in roughly the same window as
// the Modal control API.  Keep the request bounded, but allow the adapter to
// finish authentication, volume initialization, and its idempotent submission
// claim before the Sites edge aborts the transport.  Provider work itself is
// spawned asynchronously and is not covered by this HTTP timeout.
const REQUEST_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 64 * 1024;
const TOOL = /^(?:experiment_(?:capabilities|prepare|submit|status|result|artifact|cancel|list)|runpod_queue_request|training_(?:submit|status|artifact|cancel|checkpoint))$/;
const PROVIDER_ADAPTER_HOSTNAME =
  "unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";

// GATEWAY_DELEGATION_* error codes are retained because clients and stored
// diagnostics already consume them. This transport calls the Modal provider
// adapter; it is separate from the legacy Gateway service.

export function canonical(value) {
  return canonicalJson(value, "GATEWAY_DELEGATION_INVALID_ARGUMENTS");
}

function decodeBase64(value) {
  if (typeof value !== "string" || value.length > 8192 || !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) {
    throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  }
  let raw;
  try { raw = atob(value); } catch { throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED"); }
  const bytes = Uint8Array.from(raw, (character) => character.charCodeAt(0));
  if (bytes.byteLength < 32 || bytes.byteLength > 4096) throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  return bytes;
}

function endpoint(env, tool) {
  if (!TOOL.test(tool)) throw new Error("GATEWAY_DELEGATION_INVALID_TOOL");
  let base;
  try { base = new URL(env.PROVIDER_ADAPTER_URL); } catch { throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED"); }
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash ||
      (base.port && base.port !== "443") || base.hostname !== PROVIDER_ADAPTER_HOSTNAME ||
      (base.pathname !== "/" && base.pathname !== "")) {
    throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  }
  return new URL(`/internal/sites/v1/tools/${tool}`, base.origin).toString();
}

function randomHex(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function signature(payload, encodedKey) {
  const key = await crypto.subtle.importKey(
    "raw", decodeBase64(encodedKey), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const value = await crypto.subtle.sign(
    "HMAC", key, new TextEncoder().encode(canonical(payload)));
  return [...new Uint8Array(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function boundedJson(response) {
  const bytes = await readBoundedResponseBytes(response, {
    maxBytes: MAX_RESPONSE_BYTES,
    tooLargeCode: "GATEWAY_DELEGATION_RESPONSE_TOO_LARGE",
    missingBodyCode: "GATEWAY_DELEGATION_INVALID_RESPONSE",
  });
  let result;
  try { result = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE"); }
  if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
  return result;
}

export function providerAdapterConfigured(env) {
  try {
    // This is the authenticated Modal provider adapter, not the legacy
    // Gateway/PostgreSQL service.
    endpoint(env, "experiment_capabilities");
    decodeBase64(env.PROVIDER_ADAPTER_HMAC_KEY_B64);
    return typeof env.PROVIDER_ADAPTER_KEY_ID === "string" &&
      /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(env.PROVIDER_ADAPTER_KEY_ID) &&
      typeof env.PROVIDER_ADAPTER_PROXY_TOKEN_ID === "string" &&
      /^wk-[A-Za-z0-9_-]{8,}$/.test(env.PROVIDER_ADAPTER_PROXY_TOKEN_ID) &&
      typeof env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET === "string" &&
      /^ws-[A-Za-z0-9_-]{8,}$/.test(env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET);
  } catch { return false; }
}

export async function callProviderAdapterTool(env, owner, tool, argumentsValue, fetchImpl = fetch, now = null) {
  if (!providerAdapterConfigured(env)) throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  if (typeof owner !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/.test(owner) ||
      !argumentsValue || typeof argumentsValue !== "object" || Array.isArray(argumentsValue)) {
    throw new Error("GATEWAY_DELEGATION_INVALID_ARGUMENTS");
  }
  const issuedAt = now === null ? Math.floor(Date.now() / 1000) : now;
  if (!Number.isSafeInteger(issuedAt) || issuedAt < 0) throw new Error("GATEWAY_DELEGATION_INVALID_ARGUMENTS");
  const payload = {
    version: 1, key_id: env.PROVIDER_ADAPTER_KEY_ID, owner, tool,
    arguments: argumentsValue, nonce: randomHex(16), issued_at: issuedAt,
    expires_at: issuedAt + DELEGATION_TTL_SECONDS,
  };
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetchImpl(endpoint(env, tool), {
      method: "POST", redirect: "manual", signal: controller.signal,
      headers: {
        "content-type": "application/json",
        "authorization": `Bearer ${env.PROVIDER_ADAPTER_PROXY_TOKEN_ID}.${env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET}`,
        "x-gpu-control-sites-signature": await signature(payload, env.PROVIDER_ADAPTER_HMAC_KEY_B64),
      },
      body: canonical(payload),
    });
    const value = await boundedJson(response);
    if (!response.ok) {
      const code = typeof value.code === "string" && /^[a-z0-9_]{1,64}$/.test(value.code)
        ? value.code : "gateway_delegation_failed";
      throw new Error(`GATEWAY_DELEGATION_${code.toUpperCase()}`);
    }
    return value;
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("GATEWAY_DELEGATION_TIMEOUT");
    if (typeof error?.message === "string" && error.message.startsWith("GATEWAY_DELEGATION_")) throw error;
    throw new Error("GATEWAY_DELEGATION_FAILED");
  } finally { clearTimeout(timeout); }
}
