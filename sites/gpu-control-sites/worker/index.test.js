import assert from "node:assert/strict";
import test from "node:test";
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
