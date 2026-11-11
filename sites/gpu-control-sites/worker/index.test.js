import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import worker from "./index.js";

const imageDigest = `sha256:${"a".repeat(64)}`;
const sourceSha = "b".repeat(40);

function environment({ heartbeatAt, admission = "false", heartbeatDigest = imageDigest, heartbeatSha = sourceSha } = {}) {
  const heartbeat = heartbeatAt === undefined ? null : {
    last_seen_at: heartbeatAt,
    image_digest: heartbeatDigest,
    source_sha: heartbeatSha,
  };
  return {
    CPU_WORKLOAD_ADMISSION_ENABLED: admission,
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

test("advertises only the bounded, registered pretrained CPU inference contract", async () => {
  const tools = await listTools(environment());
  const prepare = tools.find((tool) => tool.name === "experiment_prepare");
  assert.equal(prepare.inputSchema.properties.workload.const, "tiny-stories-inference-v1");
  assert.deepEqual(prepare.inputSchema.properties.parameters.required, ["max_new_tokens", "prompt", "seed"]);
  assert.equal(prepare.inputSchema.properties.parameters.properties.max_new_tokens.maximum, 32);
  assert.equal(prepare.inputSchema.properties.parameters.properties.prompt.maxLength, 128);
  assert.match(prepare.description, /pretrained TinyStories 15M/);
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
        max_cost_usd: "0.00", idempotency_key: "legacy-smoke-key",
      } },
    }),
  });
  const response = await worker.fetch(request, environment());
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
        max_cost_usd: "0.00", idempotency_key: "invalid-unicode-key",
      } },
    }),
  });
  const response = await worker.fetch(request, environment());
  const rpc = await response.json();
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function inferenceResult({ modelSha256 = "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a", generatedTokens = 6 } = {}) {
  const runId = "f".repeat(32);
  const fingerprint = "a".repeat(64);
  const prompt = "Once upon a time";
  const metrics = {
    elapsed_ms: 800,
    generated_text: `${prompt}, there was a little girl`,
    generated_tokens: generatedTokens,
    max_new_tokens: 8,
    model_id: "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin",
    model_sha256: modelSha256,
    prompt_sha256: await sha256(prompt),
    seed: 61112,
    temperature: 0.8,
  };
  const identity = { run_id: runId, source_sha: sourceSha, plan_fingerprint: fingerprint, metrics };
  return {
    run_id: runId, fingerprint, prompt, metrics,
    result: {
      schema_version: 1, run_id: runId, source_sha: sourceSha, plan_fingerprint: fingerprint,
      check: "tiny-stories-inference-v1", status: "passed", gpu_used: false,
      checks: ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
        "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"],
      metrics, checksum: await sha256(canonical(identity)),
    },
  };
}

function resultEnvironment(expectedImage = imageDigest) {
  const env = environment({ admission: "true" });
  env.RUNNER_BEARER_TOKEN = "r".repeat(48);
  env.DB.prepare = (sql) => ({
    bind() {
      return {
        async first() {
          if (sql.includes("SELECT r.state")) return {
            state: "running", lease_id: "e".repeat(32), lease_expires_at: Math.floor(Date.now() / 1000) + 30,
            fingerprint: "a".repeat(64), source_sha: sourceSha, image_digest: expectedImage,
            parameters_json: JSON.stringify({ prompt: "Once upon a time", max_new_tokens: 8, seed: 61112 }),
            runtime_seconds: 30,
          };
          if (sql.includes("UPDATE runs SET state=?")) return { id: "f".repeat(32), state: "succeeded" };
          throw new Error("unexpected result query");
        },
      };
    },
  });
  env.BUCKET = { async put() { return {}; }, async delete() {} };
  return env;
}

async function postInferenceResult(value, env) {
  const now = Math.floor(Date.now() / 1000);
  return worker.fetch(new Request("https://site.invalid/runner/result", {
    method: "POST",
    headers: { authorization: `Bearer ${env.RUNNER_BEARER_TOKEN}`, "content-type": "application/json" },
    body: JSON.stringify({
      status: "passed", run_id: value.run_id, lease_id: "e".repeat(32), result: value.result,
      cleanup_confirmation: {
        absent: true, container_id: "1".repeat(12), container_name: `gpu-control-${value.run_id}`,
        image_digest: imageDigest, lease_id: "e".repeat(32), observed_at: now,
        plan_fingerprint: value.fingerprint, run_id: value.run_id, source_sha: sourceSha,
      },
    }),
  }), env);
}

test("persists only a model- and prompt-bound inference result with verified checksum", async () => {
  const value = await inferenceResult();
  const response = await postInferenceResult(value, resultEnvironment());
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true, run: { id: value.run_id, state: "succeeded" } });
});

test("rejects inference results with a different model digest or excess generated tokens", async () => {
  const wrongModel = await inferenceResult({ modelSha256: "0".repeat(64) });
  const modelResponse = await postInferenceResult(wrongModel, resultEnvironment());
  assert.equal(modelResponse.status, 400);
  const tooManyTokens = await inferenceResult({ generatedTokens: 9 });
  const tokenResponse = await postInferenceResult(tooManyTokens, resultEnvironment());
  assert.equal(tokenResponse.status, 400);
});

test("reports a matching live runner separately from disabled admission", async () => {
  const result = await capabilities(environment({ heartbeatAt: Math.floor(Date.now() / 1000) }));
  assert.equal(result.machine_state.runner_ready, true);
  assert.equal(result.machine_state.admission_enabled, false);
  assert.equal(result.machine_state.available, false);
  assert.equal(result.blocking_reason, "WORKLOAD_ADMISSION_DISABLED");
  assert.equal(result.providers[0].enabled, false);
  assert.equal(result.paid_execution, "parked");
});

test("reports a stale runner as not ready", async () => {
  const result = await capabilities(environment({ heartbeatAt: Math.floor(Date.now() / 1000) - 61 }));
  assert.equal(result.machine_state.runner_ready, false);
  assert.equal(result.blocking_reason, "RUNNER_OR_WORKLOAD_NOT_READY");
});

test("does not accept a heartbeat for another registered image", async () => {
  const result = await capabilities(environment({
    heartbeatAt: Math.floor(Date.now() / 1000),
    heartbeatDigest: `sha256:${"c".repeat(64)}`,
  }));
  assert.equal(result.machine_state.runner_ready, false);
  assert.equal(result.blocking_reason, "RUNNER_OR_WORKLOAD_NOT_READY");
});

test("reports availability only when runner, registration, and admission are ready", async () => {
  const result = await capabilities(environment({
    heartbeatAt: Math.floor(Date.now() / 1000),
    admission: "true",
  }));
  assert.equal(result.machine_state.runner_ready, true);
  assert.equal(result.machine_state.available, true);
  assert.equal(result.blocking_reason, null);
  assert.equal(result.providers[0].enabled, true);
  assert.equal(result.paid_execution, "parked");
});

test("disabled admission cancels queued work before the runner can claim it", async () => {
  const statements = [];
  const env = environment({ heartbeatAt: Math.floor(Date.now() / 1000) });
  env.RUNNER_BEARER_TOKEN = "r".repeat(48);
  env.DB.prepare = (sql) => ({
    bind(...values) {
      return {
        async run() { statements.push({ sql, values }); return { success: true }; },
        async first() { throw new Error("claim path must not read or lease a run"); },
      };
    },
  });
  const response = await worker.fetch(new Request("https://site.invalid/runner/claim", {
    method: "POST",
    headers: { authorization: `Bearer ${env.RUNNER_BEARER_TOKEN}` },
    body: "{}",
  }), env);

  assert.equal(response.status, 409);
  assert.deepEqual(await response.json(), { error: "WORKLOAD_ADMISSION_DISABLED" });
  assert.equal(statements.length, 1);
  assert.match(statements[0].sql, /SET state='cancelled'.*WHERE state='queued'/s);
  assert.equal(Number.isSafeInteger(statements[0].values[0]), true);
});

test("duplicate submit returns the succeeded run without claiming it was newly queued", async () => {
  const runId = "c".repeat(32);
  const fingerprint = "d".repeat(64);
  const env = environment({ heartbeatAt: Math.floor(Date.now() / 1000), admission: "true" });
  env.DB.prepare = (sql) => ({
    bind() {
      return {
        async first() {
          if (sql.includes("runner_heartbeats")) return {
            last_seen_at: Math.floor(Date.now() / 1000), image_digest: imageDigest, source_sha: sourceSha,
          };
          if (sql.includes("SELECT id, state, created_at FROM runs")) {
            return { id: runId, state: "succeeded", created_at: 123 };
          }
          throw new Error("unexpected query");
        },
      };
    },
  });
  env.DB.batch = async () => { throw new Error("unique plan/run constraint"); };
  const response = await worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 2, method: "tools/call",
      params: { name: "experiment_submit", arguments: { run_id: runId, plan_fingerprint: fingerprint } },
    }),
  }), env);

  assert.equal(response.status, 200);
  const rpc = await response.json();
  const result = JSON.parse(rpc.result.content[0].text);
  assert.equal(result.run_id, runId);
  assert.equal(result.machine_state.state, "succeeded");
  assert.equal(result.human_summary, "この実験は完了しています。");
});

test("submit uses the persisted state when D1 batch resolves without creating a new row", async () => {
  const runId = "e".repeat(32);
  const env = environment({ heartbeatAt: Math.floor(Date.now() / 1000), admission: "true" });
  env.DB.prepare = (sql) => ({
    bind() {
      return {
        async first() {
          if (sql.includes("runner_heartbeats")) return {
            last_seen_at: Math.floor(Date.now() / 1000), image_digest: imageDigest, source_sha: sourceSha,
          };
          if (sql.includes("SELECT id, state, created_at FROM runs")) {
            return { id: runId, state: "succeeded", created_at: 123 };
          }
          throw new Error("unexpected query");
        },
      };
    },
  });
  env.DB.batch = async () => [{ meta: { changes: 0 } }, { meta: { changes: 0 } }];
  const response = await worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 3, method: "tools/call",
      params: { name: "experiment_submit", arguments: { run_id: runId, plan_fingerprint: "f".repeat(64) } },
    }),
  }), env);

  assert.equal(response.status, 200);
  const result = JSON.parse((await response.json()).result.content[0].text);
  assert.equal(result.run_id, runId);
  assert.equal(result.machine_state.state, "succeeded");
  assert.equal(result.human_summary, "この実験は完了しています。");
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
