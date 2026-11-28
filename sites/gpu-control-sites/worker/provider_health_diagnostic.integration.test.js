import assert from "node:assert/strict";
import test from "node:test";
import worker from "./index.js";
import { MODAL_HEALTH_CHECK_COOLDOWN_SECONDS } from "./provider_health_policy.js";

const imageDigest = `sha256:${"a".repeat(64)}`;
const sourceSha = "b".repeat(40);
const modalApiUrl = "https://unjuno--gpu-control-sites-control-api.us-east.modal.run";
const healthRunId = "1".repeat(32);
const healthFingerprint = "c".repeat(64);
const healthArgs = { run_id: healthRunId, plan_fingerprint: healthFingerprint };

function authorizedHealthEnvironment({ admission = "true", alreadyChecked = false, budgetError = false, authorization = true, healthResultChanges = 1 } = {}) {
  const healthLimit = new Map();
  const checkedPlans = new Set(alreadyChecked ? [healthRunId] : []);
  let planHealthReady = null;
  const env = {
    CPU_WORKLOAD_ADMISSION_ENABLED: admission,
    CPU_WORKLOAD_SOURCE_SHA: sourceSha,
    CPU_WORKLOAD_IMAGE_DIGEST: imageDigest,
    GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,other-owner",
    MODAL_API_URL: modalApiUrl,
    MODAL_PROXY_TOKEN_ID: "wk-12345678",
    MODAL_PROXY_TOKEN_SECRET: "ws-12345678",
    MODAL_WORKLOAD_IMAGE_FINGERPRINT: "c".repeat(64),
    BUCKET: { put: async () => {} },
    DB: {
      prepare(sql) {
        return { bind(...values) { return {
          first: async () => sql.includes("FROM plans p JOIN human_authorizations a") && authorization &&
            values[0] === healthRunId && values[1] === "test-owner" && values[2] === healthFingerprint
            ? { id: healthRunId } : null,
          async run() {
            if (sql.includes("UPDATE modal_authorized_health_checks")) {
              planHealthReady = values[0];
              return { meta: { changes: healthResultChanges } };
            }
            if (sql.includes("modal_health_check_limits")) {
              if (budgetError) throw new Error("D1 health budget unavailable");
              const [now, threshold] = values;
              const prior = healthLimit.get("workspace");
              if (prior !== undefined && prior > threshold) return { meta: { changes: 0 } };
              healthLimit.set("workspace", now);
              return { meta: { changes: 1 } };
            }
            if (sql.includes("modal_authorized_health_checks")) {
              if (checkedPlans.has(healthRunId)) return { meta: { changes: 0 } };
              checkedPlans.add(healthRunId);
              return { meta: { changes: 1 } };
            }
            throw new Error("unexpected health query");
          },
        }; } };
      },
    },
    healthReadyForTest: () => planHealthReady,
  };
  return env;
}

async function toolCall(env, user, name, args) {
  return worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
    body: JSON.stringify({ jsonrpc: "2.0", id: 99, method: "tools/call", params: { name, arguments: args } }),
  }), env);
}

test("Modal health diagnostic requires an exact, unconsumed plan confirmation", async () => {
  const env = authorizedHealthEnvironment({ authorization: false });
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-12345678";
  env.MODAL_PROXY_TOKEN_SECRET = "ws-12345678";
  let called = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { called = true; return Response.json({ ready: true }); };
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.blocking_reason, "HUMAN_AUTHORIZATION_REQUIRED");
    assert.equal(result.machine_state.sandbox_started, false);
    assert.equal(called, false, "health must not call Modal before exact-plan confirmation");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal health diagnostic does not contact the provider while admission is closed", async () => {
  const env = authorizedHealthEnvironment({ admission: "false" });
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-12345678";
  env.MODAL_PROXY_TOKEN_SECRET = "ws-12345678";
  let called = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { called = true; return Response.json({ ready: true }); };
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.blocking_reason, "CPU_WORKLOAD_ADMISSION_DISABLED");
    assert.equal(result.machine_state.sandbox_started, false);
    assert.equal(called, false, "closed admission must avoid separately billed Modal health calls");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal proxy credentials are never sent to an unregistered host", async () => {
  const env = authorizedHealthEnvironment();
  env.MODAL_API_URL = "https://attacker.example.test";
  let called = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { called = true; return Response.json({ ready: true }); };
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.blocking_reason, "MODAL_PROVIDER_NOT_CONFIGURED");
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal requests reject redirects before proxy credentials can be forwarded", async () => {
  const env = authorizedHealthEnvironment();
  let redirectMode = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (_url, init) => {
    redirectMode = init.redirect;
    return new Response(null, { status: 302, headers: { location: "https://attacker.example.test/collect" } });
  };
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(redirectMode, "manual");
    assert.equal(result.blocking_reason, "MODAL_PROVIDER_HEALTH_MISMATCH");
    assert.equal(result.machine_state.checks.error_code, "MODAL_PROVIDER_HTTP_3XX");
    assert.equal(result.machine_state.sandbox_started, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal health diagnostic is owner-scoped and performs one authenticated GET per confirmed plan", async () => {
  const env = authorizedHealthEnvironment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-12345678";
  env.MODAL_PROXY_TOKEN_SECRET = "ws-12345678";
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "c".repeat(64);
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async (url, init) => {
    called = true;
    assert.equal(url, "https://unjuno--gpu-control-sites-control-api.us-east.modal.run/v1/health");
    assert.equal(init.method, "GET");
    assert.equal(init.body, undefined);
    assert.equal(init.headers.Authorization,
      `Bearer ${env.MODAL_PROXY_TOKEN_ID}.${env.MODAL_PROXY_TOKEN_SECRET}`);
    assert.equal(init.headers["Modal-Key"], undefined);
    assert.equal(init.headers["Modal-Secret"], undefined);
    return new Response(JSON.stringify({
      ready: true, provider: "modal_cpu", workload: "tiny-stories-inference-v1",
      registered_image_digest: imageDigest, image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT,
      max_runtime_seconds: 30, source_sha: sourceSha,
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    const denied = await toolCall(env, "other-owner", "experiment_provider_health", healthArgs);
    assert.equal(denied.status, 200);
    const deniedValue = JSON.parse((await denied.json()).result.content[0].text);
    assert.equal(deniedValue.blocking_reason, "HUMAN_AUTHORIZATION_REQUIRED");
    assert.equal(called, false, "unauthorized caller must not reach Modal");

    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.status, "ok", JSON.stringify(result));
    assert.equal(result.machine_state.ready, true);
    assert.equal(result.machine_state.sandbox_started, false);
    assert.equal(result.machine_state.inference_started, false);
    assert.equal(result.machine_state.control_function_cost_included_in_sandbox_ceiling, false);
    assert.equal(env.healthReadyForTest(), 1, "a successful health check is persisted for submit to reuse");
    assert.equal(called, true);
    assert.equal(JSON.stringify(result).includes(env.MODAL_PROXY_TOKEN_SECRET), false);

    const limitedResponse = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const limited = JSON.parse((await limitedResponse.json()).result.content[0].text);
    assert.equal(limited.blocking_reason, "MODAL_HEALTH_CHECK_RATE_LIMITED");
    assert.equal(called, true, "rate limited repeat must not call Modal");

    const originalNow = Date.now;
    Date.now = () => originalNow() + (MODAL_HEALTH_CHECK_COOLDOWN_SECONDS + 1) * 1000;
    try {
      const duplicateResponse = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
      const duplicate = JSON.parse((await duplicateResponse.json()).result.content[0].text);
      assert.equal(duplicate.blocking_reason, "MODAL_PLAN_HEALTH_ALREADY_CHECKED");
      assert.equal(called, true, "a confirmed plan authorizes at most one billed health call");
    } finally {
      Date.now = originalNow;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal health diagnostic reports provider auth failure without starting a Sandbox", async () => {
  const env = authorizedHealthEnvironment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-12345678";
  env.MODAL_PROXY_TOKEN_SECRET = "ws-12345678";
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "c".repeat(64);
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("credential detail must not escape", { status: 401 });
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.status, "blocked");
    assert.equal(result.machine_state.ready, false);
    assert.equal(result.machine_state.checks.request_succeeded, false);
    assert.equal(result.machine_state.checks.error_code, "MODAL_PROVIDER_HTTP_401");
    assert.equal(result.machine_state.sandbox_started, false);
    assert.equal(result.machine_state.inference_started, false);
    assert.equal(JSON.stringify(result).includes("credential detail"), false);
    assert.equal(JSON.stringify(result).includes(env.MODAL_PROXY_TOKEN_SECRET), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal health diagnostic fails closed when the reserved health row cannot be updated", async () => {
  const env = authorizedHealthEnvironment({ healthResultChanges: 0 });
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ ready: true, provider: "modal_cpu", workload: "tiny-stories-inference-v1",
    source_sha: sourceSha, registered_image_digest: imageDigest,
    image_fingerprint: "c".repeat(64), max_runtime_seconds: 30 });
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.status, "blocked");
    assert.equal(result.blocking_reason, "MODAL_HEALTH_RESULT_PERSISTENCE_FAILED");
    assert.equal(result.machine_state.sandbox_started, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal health diagnostic fails closed when the global call budget cannot be reserved", async () => {
  const env = authorizedHealthEnvironment({ budgetError: true });
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; return Response.json({ ready: true }); };
  try {
    const response = await toolCall(env, "test-owner", "experiment_provider_health", healthArgs);
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.blocking_reason, "MODAL_HEALTH_CHECK_LIMIT_UNAVAILABLE");
    assert.equal(result.machine_state.sandbox_started, false);
    assert.equal(called, false, "D1 budget reservation failure must prevent Modal access");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal health diagnostic requires the exact confirmed plan identity", async () => {
  const env = authorizedHealthEnvironment();
  let called = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { called = true; return Response.json({ ready: true }); };
  try {
    const invalid = await toolCall(env, "test-owner", "experiment_provider_health", { ...healthArgs, plan_fingerprint: "d".repeat(64) });
    const result = JSON.parse((await invalid.json()).result.content[0].text);
    assert.equal(result.blocking_reason, "HUMAN_AUTHORIZATION_REQUIRED");
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
