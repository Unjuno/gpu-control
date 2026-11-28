import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import worker from "./index.js";

const sourceSha = "b".repeat(40);

test("artifact chunks require the authenticated owner and verify stored content", async () => {
  const runId = "9".repeat(32);
  const bytes = Buffer.from('{"status":"passed","output":"hello"}', "utf8");
  const digest = createHash("sha256").update(bytes).digest("hex");
  const row = { id: runId, state: "succeeded", result_artifact_id: "result.json",
    result_artifact_sha256: digest, result_artifact_size: bytes.length,
    fingerprint: "a".repeat(64), source_sha: sourceSha };
  let bucketReads = 0;
  let corruptObject = false;
  const env = { GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,different-owner", DB: {} };
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

