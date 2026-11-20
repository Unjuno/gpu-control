const DELEGATION_TTL_SECONDS = 60;
const REQUEST_TIMEOUT_MS = 10000;
const MAX_RESPONSE_BYTES = 64 * 1024;
const TOOL = /^experiment_(?:capabilities|prepare|submit|status|result|artifact|cancel|list)$/;

export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  if (typeof value === "number" && !Number.isFinite(value)) throw new Error("GATEWAY_DELEGATION_INVALID_ARGUMENTS");
  return JSON.stringify(value);
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
  try { base = new URL(env.GATEWAY_DELEGATION_URL); } catch { throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED"); }
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash ||
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
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_RESPONSE_BYTES) throw new Error("GATEWAY_DELEGATION_RESPONSE_TOO_LARGE");
  if (!response.body) throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_RESPONSE_BYTES) {
        try { await reader.cancel(); } catch {}
        throw new Error("GATEWAY_DELEGATION_RESPONSE_TOO_LARGE");
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let result;
  try { result = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE"); }
  if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
  return result;
}

export function gatewayDelegationConfigured(env) {
  try {
    // The provider adapter is an authenticated Modal endpoint.  Do not fall
    // back to the old externally hosted Gateway/PostgreSQL deployment path.
    const adapterEnv = {
      ...env,
      GATEWAY_DELEGATION_URL: env.PROVIDER_ADAPTER_URL,
      GATEWAY_DELEGATION_KEY_ID: env.PROVIDER_ADAPTER_KEY_ID,
      GATEWAY_DELEGATION_HMAC_KEY_B64: env.PROVIDER_ADAPTER_HMAC_KEY_B64,
    };
    endpoint(adapterEnv, "experiment_capabilities");
    decodeBase64(adapterEnv.GATEWAY_DELEGATION_HMAC_KEY_B64);
    return typeof adapterEnv.GATEWAY_DELEGATION_KEY_ID === "string" &&
      /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(adapterEnv.GATEWAY_DELEGATION_KEY_ID) &&
      typeof env.PROVIDER_ADAPTER_PROXY_TOKEN_ID === "string" &&
      /^wk-[A-Za-z0-9_-]{8,}$/.test(env.PROVIDER_ADAPTER_PROXY_TOKEN_ID) &&
      typeof env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET === "string" &&
      /^ws-[A-Za-z0-9_-]{8,}$/.test(env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET);
  } catch { return false; }
}

export async function delegateGatewayTool(env, owner, tool, argumentsValue, fetchImpl = fetch, now = null) {
  if (!gatewayDelegationConfigured(env)) throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  const adapterEnv = {
    ...env,
    GATEWAY_DELEGATION_URL: env.PROVIDER_ADAPTER_URL,
    GATEWAY_DELEGATION_KEY_ID: env.PROVIDER_ADAPTER_KEY_ID,
    GATEWAY_DELEGATION_HMAC_KEY_B64: env.PROVIDER_ADAPTER_HMAC_KEY_B64,
  };
  if (typeof owner !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/.test(owner) ||
      !argumentsValue || typeof argumentsValue !== "object" || Array.isArray(argumentsValue)) {
    throw new Error("GATEWAY_DELEGATION_INVALID_ARGUMENTS");
  }
  const issuedAt = now === null ? Math.floor(Date.now() / 1000) : now;
  if (!Number.isSafeInteger(issuedAt) || issuedAt < 0) throw new Error("GATEWAY_DELEGATION_INVALID_ARGUMENTS");
  const payload = {
    version: 1, key_id: adapterEnv.GATEWAY_DELEGATION_KEY_ID, owner, tool,
    arguments: argumentsValue, nonce: randomHex(16), issued_at: issuedAt,
    expires_at: issuedAt + DELEGATION_TTL_SECONDS,
  };
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetchImpl(endpoint(adapterEnv, tool), {
      method: "POST", redirect: "manual", signal: controller.signal,
      headers: {
        "content-type": "application/json",
        "authorization": `Bearer ${env.PROVIDER_ADAPTER_PROXY_TOKEN_ID}.${env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET}`,
        "x-gpu-control-sites-signature": await signature(payload, adapterEnv.GATEWAY_DELEGATION_HMAC_KEY_B64),
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
