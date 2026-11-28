import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { persistGoogleColabArtifacts, readGoogleColabArtifact } from "./google_colab_artifacts.js";

const runId = "a".repeat(32);
const fingerprint = "b".repeat(64);
const owner = "colab-artifact-owner";
const bytes = new TextEncoder().encode("verified colab output");
const sha256 = createHash("sha256").update(bytes).digest("hex");

test("Colab artifact persistence and retrieval keep owner binding and verify the full object", async () => {
  const objects = new Map();
  const row = { run_id: runId, artifact_id: "artifact-01", object_key: `colab/runs/${runId}/${fingerprint}/artifact-01`,
    sha256, size_bytes: bytes.byteLength, fingerprint, provider_state: "succeeded" };
  const env = {
    BUCKET: {
      async put(key, value, { customMetadata }) {
        objects.set(key, { bytes: new Uint8Array(value), size: value.byteLength, customMetadata });
      },
      async get(key) {
        const value = objects.get(key);
        return value && { size: value.size, customMetadata: value.customMetadata,
          async arrayBuffer() { return value.bytes.slice().buffer; } };
      },
    },
    DB: {
      prepare(sql) {
        return { bind(...values) {
          return {
            async run() {
              assert.match(sql, /INSERT OR IGNORE INTO google_colab_run_artifacts/);
              assert.deepEqual(values, [runId, owner, fingerprint, "artifact-01", "metrics.json",
                row.object_key, sha256, bytes.byteLength, 100]);
              return { meta: { changes: 1 } };
            },
            async first() {
              if (sql.includes("JOIN gateway_delegated_plans")) {
                return values[0] === owner && values[1] === runId && values[2] === "artifact-01" ? row : null;
              }
              return values[0] === owner && values[1] === runId ? { id: runId } : null;
            },
          };
        } };
      },
    },
  };
  const runtime = { name: `runtimes/gpu-control-${runId.slice(0, 24)}`,
    runtimeSpec: { variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD" },
    connectionInfo: { token: "runtime-token-for-test", expireTime: "2027-01-01T00:00:00Z",
      url: "https://colab.googleusercontent.com/runtime" } };
  const saved = await persistGoogleColabArtifacts(env, owner, runId, fingerprint, runtime,
    { artifacts: [{ path: "metrics.json", size_bytes: bytes.byteLength, sha256 }] },
    async (url) => {
      assert.equal(new URL(url).pathname, "/runtime/files/metrics.json");
      return new Response(bytes);
    }, 100);
  assert.deepEqual(saved, [{ artifact_id: "artifact-01", path: "metrics.json", sha256,
    size_bytes: bytes.byteLength }]);
  assert.deepEqual(objects.get(row.object_key).customMetadata,
    { run_id: runId, owner_id: owner, plan_fingerprint: fingerprint, artifact_id: "artifact-01", sha256 });

  const result = await readGoogleColabArtifact(env, owner,
    { run_id: runId, artifact_id: "artifact-01", offset: 0, max_bytes: 8 });
  assert.equal(result.status, "ok");
  assert.equal(result.machine_state.sha256, sha256);
  assert.equal(Buffer.from(result.machine_state.data, "base64").toString(), "verified");
  assert.equal(result.machine_state.eof, false);
  assert.equal(await readGoogleColabArtifact(env, "another-owner",
    { run_id: runId, artifact_id: "artifact-01", offset: 0, max_bytes: 8 }), null);

  objects.get(row.object_key).bytes[0] ^= 1;
  await assert.rejects(() => readGoogleColabArtifact(env, owner,
    { run_id: runId, artifact_id: "artifact-01", offset: 0, max_bytes: 8 }), /ARTIFACT_CHECKSUM_MISMATCH/);
});
