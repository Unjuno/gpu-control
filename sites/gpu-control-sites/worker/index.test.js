import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import worker from "./index.js";

const imageDigest = `sha256:${"a".repeat(64)}`;
const sourceSha = "b".repeat(40);

function environment({ heartbeatAt, admission = "false", heartbeatDigest = imageDigest, heartbeatSha = sourceSha, cancellationProtocol = 1 } = {}) {
  const heartbeat = heartbeatAt === undefined ? null : {
    last_seen_at: heartbeatAt,
    image_digest: heartbeatDigest,
    source_sha: heartbeatSha,
    cancellation_protocol: cancellationProtocol,
  };
  return {
    CPU_WORKLOAD_ADMISSION_ENABLED: admission,
    GPU_CONTROL_ALLOWED_USER_IDS: "test-owner",
    CPU_WORKLOAD_REPOSITORY: "Unjuno/gpu-control",
    CPU_WORKLOAD_SOURCE_SHA: sourceSha,
    CPU_WORKLOAD_IMAGE_DIGEST: imageDigest,
    DB: {
      prepare() {
        return { bind() { return { first: async () => heartbeat }; } };
      },
    },
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

async function capabilities(env) {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "experiment_capabilities", arguments: {} },
    }),
  });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 200);
  const envelope = JSON.parse((await response.json()).result.content[0].text);
  return envelope;
}

async function toolCall(env, user, name, args) {
  return worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
    body: JSON.stringify({ jsonrpc: "2.0", id: 99, method: "tools/call", params: { name, arguments: args } }),
  }), env);
}

test("public MCP data tools reject anonymous callers before touching D1", async () => {
  const env = environment();
  let databaseReads = 0;
  env.DB.prepare = () => {
    databaseReads++;
    throw new Error("anonymous request reached D1");
  };
  const response = await worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 7, method: "tools/call",
      params: { name: "experiment_list", arguments: {} },
    }),
  }), env);
  const rpc = await response.json();

  assert.equal(response.status, 200);
  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "AUTHENTICATED_SITE_USER_REQUIRED" });
  assert.equal(databaseReads, 0);
});

test("MCP tool annotations distinguish read, execution, and lifecycle operations", async () => {
  const response = await worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
  }), environment());
  const rpc = await response.json();
  assert.equal(response.status, 200);
  const tools = Object.fromEntries(rpc.result.tools.map((item) => [item.name, item.annotations]));

  for (const name of ["experiment_capabilities", "experiment_artifact", "experiment_list"]) {
    assert.equal(tools[name].readOnlyHint, true, `${name} should be read-only`);
    assert.equal(tools[name].destructiveHint, false, `${name} should not be destructive`);
    assert.equal(tools[name].idempotentHint, true, `${name} should be idempotent`);
    assert.equal(tools[name].openWorldHint, false, `${name} uses only bounded resources`);
  }
  assert.deepEqual(tools.experiment_prepare, {
    readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false,
  });
  assert.deepEqual(tools.experiment_submit, {
    readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: false,
  });
  for (const name of ["experiment_status", "experiment_result"]) {
    assert.equal(tools[name].readOnlyHint, false, `${name} synchronizes provider state into D1/R2`);
    assert.equal(tools[name].destructiveHint, false, `${name} does not cancel or allocate by intent`);
    assert.equal(tools[name].idempotentHint, false, `${name} may advance a live run`);
    assert.equal(tools[name].openWorldHint, false, `${name} uses only the configured provider`);
  }
  assert.deepEqual(tools.experiment_cancel, {
    readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: false,
  });
});

test("authenticated users outside the configured owner allowlist cannot touch D1", async () => {
  const env = environment();
  let databaseReads = 0;
  env.DB.prepare = () => {
    databaseReads++;
    throw new Error("unauthorized Site user reached D1");
  };
  const response = await toolCall(env, "another-chatgpt-user", "experiment_list", {});
  const rpc = await response.json();

  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "SITE_USER_NOT_AUTHORIZED" });
  assert.equal(databaseReads, 0);
});

test("Modal response bodies are byte-bounded and cancelled as soon as the limit is exceeded", async () => {
  const env = environment({ admission: "true" });
  env.MODAL_PROVIDER_ADMISSION_ENABLED = "true";
  env.MODAL_API_URL = "https://modal.invalid";
  env.MODAL_PROXY_TOKEN_ID = "wk-" + "t".repeat(16);
  env.MODAL_PROXY_TOKEN_SECRET = "ws-" + "s".repeat(16);
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  let cancelCalls = 0;
  try {
    globalThis.fetch = async () => new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("x".repeat(4096)));
        controller.enqueue(new TextEncoder().encode("y".repeat(4097)));
      },
      cancel() { cancelCalls++; },
    }));
    const result = await capabilities(env);
    assert.equal(result.machine_state.provider_ready, false);
    assert.equal(cancelCalls, 1);

    globalThis.fetch = async () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode("x".repeat(8193))); },
      cancel() { cancelCalls++; },
    }), { headers: { "content-length": "8193" } });
    const declaredSizeResult = await capabilities(env);
    assert.equal(declaredSizeResult.machine_state.provider_ready, false);
    assert.equal(cancelCalls, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("health can be verified while Modal admission remains disabled", async () => {
  const env = environment();
  env.MODAL_API_URL = "https://modal.invalid";
  env.MODAL_PROXY_TOKEN_ID = "wk-" + "t".repeat(16);
  env.MODAL_PROXY_TOKEN_SECRET = "ws-" + "s".repeat(16);
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (_url, init) => {
      assert.equal(new Headers(init.headers).get("modal-key"), env.MODAL_PROXY_TOKEN_ID);
      assert.equal(new Headers(init.headers).get("modal-secret"), env.MODAL_PROXY_TOKEN_SECRET);
      return Response.json({ ready: true, provider: "modal_cpu", workload: "tiny-stories-inference-v1",
        source_sha: sourceSha, registered_image_digest: imageDigest,
        image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT, max_runtime_seconds: 30 });
    };
    const result = await capabilities(env);
    assert.equal(result.machine_state.provider_ready, true);
    assert.deepEqual(result.machine_state.provider_health_checks, {
      configured: true, ready: true, provider: true, workload: true,
      registered_image_digest: true, image_fingerprint: true, max_runtime_seconds: true, source_sha: true,
    });
    assert.equal(result.machine_state.admission_enabled, false);
    assert.equal(result.machine_state.available, false);
    assert.equal(result.machine_state.free, false);
    assert.equal(result.machine_state.paid, true);
    assert.equal(result.machine_state.credit_eligible, true);
    assert.equal(result.machine_state.estimated_max_sandbox_cost_usd, "0.0013");
    assert.equal(result.providers[0].paid, true);
    assert.equal(result.providers[0].credit_eligible, true);
    assert.equal(result.blocking_reason, "CPU_WORKLOAD_ADMISSION_DISABLED");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("stores a bounded Modal exit-code diagnostic without exposing provider stderr", async () => {
  const runId = "f".repeat(32);
  const current = { id: runId, state: "running", created_at: 10, updated_at: 11,
    result_json: null, failure_code: null, cleanup_state: "pending", cancel_requested: 0,
    result_artifact_id: null, result_artifact_sha256: null, result_artifact_size: null,
    lease_id: null, workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control",
    source_sha: "b".repeat(40), image_digest: `sha256:${"a".repeat(64)}`,
    parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }),
    fingerprint: "c".repeat(64), runtime_seconds: 10, idempotency_key: "diagnostic-test" };
  const env = environment();
  env.MODAL_API_URL = "https://modal.invalid";
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "d".repeat(64);
  env.BUCKET = { put: async () => {} };
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async first() {
      if (sql.includes("FROM runs r JOIN plans p")) return { ...current };
      throw new Error(`unexpected D1 first query: ${sql}`);
    },
    async run() {
      if (sql.startsWith("UPDATE runs SET lease_id=")) {
        current.lease_id = values[0];
        return { success: true };
      }
      if (sql.includes("SET state='failed', failure_code=?")) {
        [current.failure_code, current.updated_at] = values;
        current.state = "failed";
        current.cleanup_state = "confirmed";
        return { success: true };
      }
      throw new Error(`unexpected D1 write query: ${sql}`);
    },
  }; } });

  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ state: "failed", exit_code: 2,
      diagnostic_code: "PREFLIGHT_RETURN_LINE_68",
      stderr: "private-provider-diagnostic-must-not-leak", sandbox_id: "sb-failed",
      cleanup_state: "confirmed" });
    const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const rpc = await response.json();
    const result = JSON.parse(rpc.result.content[0].text);
    assert.equal(result.machine_state.state, "failed");
    assert.equal(result.machine_state.failure_code, "MODAL_WORKLOAD_EXIT_2_PREFLIGHT_RETURN_LINE_68");
    assert.equal(result.machine_state.cleanup_state, "confirmed");
    assert.doesNotMatch(JSON.stringify(result), /private-provider-diagnostic-must-not-leak/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("retries Modal result persistence after an R2 or D1 write failure", async () => {
  const runId = "e".repeat(32);
  const fingerprint = "f".repeat(64);
  const parameters = { prompt: "Once", max_new_tokens: 1, seed: 1 };
  const checks = ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
    "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"];
  const metrics = { model_id: "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin",
    model_sha256: "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a",
    max_new_tokens: 1, seed: 1, generated_text: "A", generated_tokens: 1, prompt_sha256: "1".repeat(64) };
  const resultCore = { schema_version: 1, run_id: runId, source_sha: sourceSha, plan_fingerprint: fingerprint,
    check: "tiny-stories-inference-v1", status: "passed", gpu_used: false, checks, metrics };
  const result = { ...resultCore,
    checksum: createHash("sha256").update(canonicalJson({ run_id: runId, source_sha: sourceSha,
      plan_fingerprint: fingerprint, metrics })).digest("hex") };
  const joined = { id: runId, state: "running", cancel_requested: 0, workload: "tiny-stories-inference-v1",
    repository: "Unjuno/gpu-control", source_sha: sourceSha, image_digest: imageDigest, fingerprint,
    parameters_json: JSON.stringify(parameters), runtime_seconds: 10, lease_id: null };

  for (const fault of ["r2", "d1"]) {
    const env = environment({ admission: "true" });
    env.MODAL_API_URL = "https://modal.invalid";
    env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
    env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
    env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "a".repeat(64);
    let bucketWrites = 0;
    env.BUCKET = { put: async () => {
      if (fault === "r2" && bucketWrites++ === 0) throw new Error("injected R2 write failure");
      if (fault === "d1") bucketWrites++;
      return {};
    } };
    let finalizeWrites = 0;
    const current = { ...joined };
    env.DB.prepare = (sql) => ({ bind(...values) {
      return {
        async first() {
          if (sql.includes("FROM runs r JOIN plans p")) return { ...current };
          throw new Error(`unexpected D1 first query: ${sql}`);
        },
        async run() {
          if (sql.startsWith("UPDATE runs SET lease_id=")) {
            current.lease_id = values[0];
            return { success: true };
          }
          if (sql.startsWith("UPDATE runs SET state='succeeded'")) {
            if (fault === "d1" && finalizeWrites++ === 0) throw new Error("injected D1 finalize failure");
            current.state = "succeeded";
            current.result_json = values[0];
            current.result_artifact_id = values[1];
            current.result_artifact_sha256 = values[2];
            current.result_artifact_size = values[3];
            current.cleanup_state = "confirmed";
            return { success: true };
          }
          throw new Error(`unexpected D1 write query: ${sql}`);
        },
      };
    } });

    const originalFetch = globalThis.fetch;
    let providerReads = 0;
    try {
      globalThis.fetch = async (url, init) => {
        assert.match(String(url), new RegExp(`/v1/runs/${runId}/status$`));
        assert.equal(new Headers(init.headers).get("modal-key"), env.MODAL_PROXY_TOKEN_ID);
        providerReads++;
        return Response.json({ state: "succeeded", cleanup_state: "confirmed", sandbox_id: "sb-terminal", result });
      };
      const firstResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
      const firstRpc = await firstResponse.json();
      assert.equal(firstRpc.result.isError, true, `${fault} failure must remain visible`);
      assert.equal(current.state, "running", `${fault} failure must not mark an unpersisted result successful`);

      const retryResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
      const retryRpc = await retryResponse.json();
      assert.equal(retryRpc.result.isError, false);
      assert.equal(JSON.parse(retryRpc.result.content[0].text).machine_state.state, "succeeded");
      assert.equal(current.state, "succeeded");
      assert.equal(providerReads, 2, "retry must reconcile the same deterministic Modal run");
      assert.equal(bucketWrites, 2);
    } finally {
      globalThis.fetch = originalFetch;
    }
  }
});

function cancellationEnvironment(initialState) {
  const run = { id: "c".repeat(32), owner_id: "test-owner", state: initialState,
    cancel_requested: 0, cleanup_state: "pending", lease_id: "d".repeat(32) };
  let updates = 0;
  const env = environment();
  env.DB.prepare = (sql) => ({
    bind(...values) {
      return {
        async first() {
          if (sql.includes("SELECT") && sql.includes("FROM runs") && sql.includes("owner_id")) {
            return values.includes("test-owner") && values.includes(run.id) ? { ...run } : null;
          }
          if (sql.includes("UPDATE runs SET state='cancelled'") && run.state === "queued") {
            updates++;
            run.state = "cancelled";
            run.failure_code = "caller_cancelled_before_start";
            run.cleanup_state = "confirmed";
            return { id: run.id, state: run.state, cleanup_state: run.cleanup_state };
          }
          if (sql.includes("UPDATE runs SET cancel_requested=1") && run.state === "running") {
            updates++;
            run.cancel_requested = 1;
            return { id: run.id, state: run.state, cancel_requested: 1 };
          }
          return null;
        },
      };
    },
  });
  return { env, run, updates: () => updates };
}

test("cancels a queued owned run without asking Runner to clean up a container", async () => {
  const { env, run, updates } = cancellationEnvironment("queued");
  const response = await toolCall(env, "test-owner", "experiment_cancel", { run_id: run.id });
  const rpc = await response.json();
  const result = JSON.parse(rpc.result.content[0].text);

  assert.equal(result.status, "ok");
  assert.equal(result.machine_state.state, "cancelled");
  assert.equal(result.machine_state.cleanup_state, "confirmed");
  assert.equal(updates(), 1);
});

test("requests cooperative cancellation for an owned running run", async () => {
  const { env, run, updates } = cancellationEnvironment("running");
  const response = await toolCall(env, "test-owner", "experiment_cancel", { run_id: run.id });
  const rpc = await response.json();
  const result = JSON.parse(rpc.result.content[0].text);

  assert.equal(result.status, "pending");
  assert.equal(result.machine_state.state, "running");
  assert.equal(result.machine_state.cancellation_requested, true);
  assert.equal(updates(), 1);
});

test("does not let another Site user cancel an owned run", async () => {
  const { env, run, updates } = cancellationEnvironment("queued");
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,other-owner";
  const response = await toolCall(env, "other-owner", "experiment_cancel", { run_id: run.id });
  const rpc = await response.json();

  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "RUN_NOT_FOUND" });
  assert.equal(updates(), 0);
});

test("does not advertise cancellation for a terminal run", async () => {
  const runId = "d".repeat(32);
  const env = environment();
  env.DB.prepare = (sql) => ({ bind() { return { async first() {
    assert.match(sql, /owner_id = \?/);
    return { id: runId, state: "cancelled", created_at: 10, updated_at: 11, result_json: null,
      failure_code: "caller_cancelled", cleanup_state: "confirmed", cancel_requested: 0,
      result_artifact_id: null, result_artifact_sha256: null, result_artifact_size: null,
      workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control", source_sha: sourceSha,
      image_digest: imageDigest, parameters_json: JSON.stringify({ prompt: "A", max_new_tokens: 1, seed: 1 }) };
  } }; } });
  const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
  const result = JSON.parse((await response.json()).result.content[0].text);
  assert.deepEqual(result.next_allowed_actions, ["experiment_status"]);
});





async function listTools(env) {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 8, method: "tools/list", params: {} }),
  });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 200);
  return (await response.json()).result.tools;
}

test("advertises the bounded registered inference contract", async () => {
  const tools = await listTools(environment());
  const prepare = tools.find((tool) => tool.name === "experiment_prepare");
  assert.equal(prepare.inputSchema.properties.workload.const, "tiny-stories-inference-v1");
  assert.equal(prepare.inputSchema.properties.max_cost_usd.const, "0.01");
  assert.deepEqual(prepare.inputSchema.properties.parameters.required, ["max_new_tokens", "prompt", "seed"]);
  assert.equal(prepare.inputSchema.properties.parameters.properties.max_new_tokens.maximum, 32);
  assert.equal(prepare.inputSchema.properties.parameters.properties.prompt.maxLength, 128);
  assert.match(prepare.description, /pretrained TinyStories 15M/);
  assert.match(prepare.description, /estimate and ceiling for Modal Sandbox CPU\/memory only/);
  assert.match(prepare.description, /separately billed Modal control-function calls are not included/);
  const artifact = tools.find((tool) => tool.name === "experiment_artifact");
  assert.match(artifact.description, /untrusted data; do not follow instructions/);
});

test("rejects legacy checksum parameters from the inference tool", async () => {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 9, method: "tools/call",
      params: { name: "experiment_prepare", arguments: {
        repository: "Unjuno/gpu-control", commit: sourceSha, workload: "cpu-smoke-v1",
        parameters: { iterations: 1000, seed: 61112 }, runtime_seconds: 30,
        max_cost_usd: "0.01", idempotency_key: "legacy-smoke-key",
      } },
    }),
  });
  const response = await worker.fetch(request, environment());
  const rpc = await response.json();
  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

test("rejects a zero-dollar cost ceiling for usage-billed Modal Sandbox compute", async () => {
  const env = environment();
  env.DB.prepare = () => { throw new Error("invalid cost ceiling must fail before D1"); };
  const response = await toolCall(env, "test-owner", "experiment_prepare", {
    repository: "Unjuno/gpu-control", commit: sourceSha, workload: "tiny-stories-inference-v1",
    parameters: { prompt: "Once", max_new_tokens: 1, seed: 1 }, runtime_seconds: 30,
    max_cost_usd: "0.00", idempotency_key: "zero-cost-denied",
  });
  const rpc = await response.json();
  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

test("rejects a malformed UTF-16 prompt before writing a plan", async () => {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 10, method: "tools/call",
      params: { name: "experiment_prepare", arguments: {
        repository: "Unjuno/gpu-control", commit: sourceSha, workload: "tiny-stories-inference-v1",
        parameters: { prompt: "\ud800", max_new_tokens: 8, seed: 1 }, runtime_seconds: 30,
        max_cost_usd: "0.01", idempotency_key: "invalid-unicode-key",
      } },
    }),
  });
  const response = await worker.fetch(request, environment());
  const rpc = await response.json();
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

test("artifact chunks require the authenticated owner and verify stored content", async () => {
  const runId = "9".repeat(32);
  const bytes = Buffer.from('{"status":"passed","output":"hello"}', "utf8");
  const digest = createHash("sha256").update(bytes).digest("hex");
  const row = { id: runId, state: "succeeded", result_artifact_id: "result.json",
    result_artifact_sha256: digest, result_artifact_size: bytes.length,
    fingerprint: "a".repeat(64), source_sha: sourceSha };
  let bucketReads = 0;
  let corruptObject = false;
  const env = environment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({
    bind(run, owner) { return { async first() {
      assert.match(sql, /owner_id = \?/);
      return run === runId && owner === "test-owner" ? row : null;
    } }; },
  });
  env.BUCKET = { async get(key) {
    bucketReads++;
    assert.equal(key, `runs/${runId}/${digest}/result.json`);
    return { size: bytes.length, customMetadata: { run_id: runId, sha256: digest,
      plan_fingerprint: row.fingerprint, source_sha: sourceSha },
      async arrayBuffer() {
        const value = corruptObject ? Buffer.from('{"status":"failed","output":"hello"}', "utf8") : bytes;
        return value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
      } };
  } };

  async function artifactCall(user, args) {
    return worker.fetch(new Request("https://site.invalid/mcp", {
      method: "POST",
      headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
      body: JSON.stringify({ jsonrpc: "2.0", id: 42, method: "tools/call",
        params: { name: "experiment_artifact", arguments: args } }),
    }), env);
  }

  const args = { run_id: runId, artifact_id: "result.json", offset: 0, max_bytes: 12 };
  const response = await artifactCall("test-owner", args);
  const rpc = await response.json();
  assert.equal(rpc.result.isError, false);
  const result = JSON.parse(rpc.result.content[0].text);
  assert.equal(result.status, "ok");
  assert.equal(result.machine_state.sha256, digest);
  assert.equal(result.machine_state.size_bytes, bytes.length);
  assert.equal(Buffer.from(result.machine_state.data, "base64").toString("utf8"), bytes.subarray(0, 12).toString("utf8"));
  assert.equal(result.machine_state.eof, false);

  const denied = await artifactCall("different-owner", args);
  const deniedRpc = await denied.json();
  assert.equal(deniedRpc.result.isError, true);
  assert.equal(bucketReads, 1);

  corruptObject = true;
  const tampered = await artifactCall("test-owner", args);
  const tamperedRpc = await tampered.json();
  assert.equal(tamperedRpc.result.isError, true);
  assert.equal(bucketReads, 2);
});

test("another Site user cannot read an owned run status or result", async () => {
  const runId = "8".repeat(32);
  const privateMarker = "owner-private-result-marker";
  const row = {
    id: runId, state: "succeeded", created_at: 1, updated_at: 2,
    result_json: JSON.stringify({ output: privateMarker }), failure_code: null,
    cleanup_state: "confirmed", cancel_requested: 0, result_artifact_id: null,
    result_artifact_sha256: null, result_artifact_size: null,
    workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control",
    source_sha: sourceSha, image_digest: imageDigest,
    parameters_json: JSON.stringify({ prompt: "private", max_new_tokens: 1, seed: 1 }),
  };
  const env = environment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({ bind(run, owner) { return { async first() {
    assert.match(sql, /r\.owner_id = \?/);
    assert.equal(run, runId);
    return owner === "test-owner" ? row : null;
  } }; } });

  for (const name of ["experiment_status", "experiment_result"]) {
    const response = await toolCall(env, "different-owner", name, { run_id: runId });
    const rpc = await response.json();
    assert.equal(rpc.result.isError, true);
    assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "RUN_NOT_FOUND" });
    assert.equal(JSON.stringify(rpc).includes(privateMarker), false);
  }
});

test("experiment_list returns no other owner's run metadata", async () => {
  const env = environment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({ bind(owner) { return { async all() {
    assert.match(sql, /WHERE r\.owner_id = \?/);
    assert.equal(owner, "different-owner");
    return { results: [] };
  } }; } });

  const response = await toolCall(env, "different-owner", "experiment_list", {});
  const rpc = await response.json();
  assert.equal(rpc.result.isError, false);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text).machine_state.experiments, []);
});

test("prepare idempotency keys are isolated by Site owner", async () => {
  const plans = new Map();
  const env = environment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({ bind(...values) {
    if (sql.includes("INSERT OR IGNORE INTO plans")) {
      assert.match(sql, /owner_id/);
      return { async run() {
        const [id, owner, key, fingerprint, , , , digest] = values;
        const mapKey = `${owner}:${key}`;
        if (!plans.has(mapKey)) plans.set(mapKey, { id, fingerprint, image_digest: digest,
          state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 300 });
      } };
    }
    assert.match(sql, /WHERE owner_id = \? AND idempotency_key = \?/);
    return { async first() { return plans.get(`${values[0]}:${values[1]}`) || null; } };
  } });

  const args = { repository: "Unjuno/gpu-control", commit: sourceSha,
    workload: "tiny-stories-inference-v1",
    parameters: { prompt: "A", max_new_tokens: 1, seed: 1 },
    runtime_seconds: 10, max_cost_usd: "0.01", idempotency_key: "same-key-0001" };
  const firstResult = JSON.parse((await (await toolCall(env, "test-owner", "experiment_prepare", args)).json()).result.content[0].text);
  const secondResult = JSON.parse((await (await toolCall(env, "different-owner", "experiment_prepare", args)).json()).result.content[0].text);
  const first = firstResult.machine_state;
  const second = secondResult.machine_state;

  assert.equal(first.state, "prepared");
  assert.equal(second.state, "prepared");
  assert.equal(first.estimated_sandbox_cost_usd, "0.0005");
  assert.equal(first.max_sandbox_cost_usd, "0.01");
  assert.equal(first.control_function_cost_included, false);
  assert.equal(first.cost_is_estimate, true);
  assert.equal(first.credit_eligible, true);
  assert.notEqual(first.run_id, second.run_id);
  assert.equal(plans.size, 2);
});



test("keeps Modal submission blocked until the provider is configured", async () => {
  const env = environment();
  let writes = 0;
  env.DB.batch = async () => { writes++; throw new Error("blocked submission must not write"); };
  const response = await toolCall(env, "test-owner", "experiment_submit", {
    run_id: "f".repeat(32), plan_fingerprint: "a".repeat(64),
  });
  const rpc = await response.json();
  assert.equal(rpc.result.isError, false);
  const result = JSON.parse(rpc.result.content[0].text);
  assert.equal(result.status, "blocked");
  assert.equal(result.blocking_reason, "MODAL_PROVIDER_NOT_CONFIGURED");
  assert.equal(writes, 0);
});

test("retired Runner routes stay closed even when a legacy bearer is supplied", async () => {
  const env = environment();
  env.RUNNER_BEARER_TOKEN = "x".repeat(48);
  env.DB.prepare = () => { throw new Error("retired route reached D1"); };
  for (const path of ["/runner/heartbeat", "/runner/claim", "/runner/result"]) {
    const response = await worker.fetch(new Request(`https://site.invalid${path}`, {
      method: "POST", headers: { authorization: `Bearer ${env.RUNNER_BEARER_TOKEN}` }, body: "{}",
    }), env);
    assert.equal(response.status, 404, path);
    assert.deepEqual(await response.json(), { error: "NOT_FOUND" });
  }
});
