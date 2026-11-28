import assert from "node:assert/strict";
import test from "node:test";
import { persistRunResultArtifact, readRunResultArtifact, RUN_ARTIFACT_MAX_BYTES } from "./run_artifacts.js";

const runId = "a".repeat(32);
const ownerId = "owner";
const sourceSha = "b".repeat(40);
const fingerprint = "c".repeat(64);
const resultJson = JSON.stringify({ run_id: runId, status: "passed" });

function storage({ updateChanges = 1, currentRun = null } = {}) {
  const objects = new Map();
  const run = currentRun || { state: "running", cancel_requested: 0 };
  const env = {
    DB: { prepare(sql) { return { bind(...values) { return {
      async run() {
        if (sql.startsWith("UPDATE runs SET state='succeeded'")) {
          if (updateChanges === 1) Object.assign(run, { state: "succeeded", result_json: values[0],
            result_artifact_id: values[1], result_artifact_sha256: values[2], result_artifact_size: values[3],
            cleanup_state: "confirmed", updated_at: values[4] });
          return { meta: { changes: updateChanges } };
        }
        throw new Error("unexpected write");
      },
      async first() {
        if (sql.startsWith("SELECT state, cancel_requested FROM runs")) return run;
        if (sql.includes("FROM runs r JOIN plans p")) return run.artifactRow || null;
        throw new Error("unexpected read");
      },
    }; } }; } },
    BUCKET: {
      async put(key, body, options) { objects.set(key, { bytes: new Uint8Array(body), metadata: options.customMetadata }); },
      async get(key) {
        const object = objects.get(key);
        return object && { size: object.bytes.length, customMetadata: object.metadata,
          async arrayBuffer() { return object.bytes.slice().buffer; } };
      },
      async delete(key) { objects.delete(key); },
    },
  };
  return { env, objects, run };
}

test("run artifact persistence writes immutable metadata and only then finalizes the owner run", async () => {
  const { env, objects, run } = storage();
  const stored = await persistRunResultArtifact(env, { runId, ownerId, sourceSha, planFingerprint: fingerprint,
    resultJson, now: 1_800_000_000 });
  assert.equal(stored.size_bytes, new TextEncoder().encode(resultJson).byteLength);
  assert.equal(stored.artifact_id, "result-json-v1");
  assert.equal(objects.size, 1);
  assert.equal(run.state, "succeeded");
  assert.equal(run.result_artifact_sha256, stored.sha256);
  assert.deepEqual([...objects.values()][0].metadata, { run_id: runId, sha256: stored.sha256,
    plan_fingerprint: fingerprint, source_sha: sourceSha });
});

test("run artifact storage removes an object only when cancellation won finalization", async () => {
  const { env, objects } = storage({ updateChanges: 0, currentRun: { state: "running", cancel_requested: 1 } });
  const result = await persistRunResultArtifact(env, { runId, ownerId, sourceSha, planFingerprint: fingerprint,
    resultJson, now: 1_800_000_000 });
  assert.equal(result, null);
  assert.equal(objects.size, 0);
});

test("run artifact reads recheck owner metadata and the complete checksum before returning a chunk", async () => {
  const { env, objects, run } = storage();
  const stored = await persistRunResultArtifact(env, { runId, ownerId, sourceSha, planFingerprint: fingerprint,
    resultJson, now: 1_800_000_000 });
  run.artifactRow = { id: runId, state: "succeeded", result_artifact_id: stored.artifact_id,
    result_artifact_sha256: stored.sha256, result_artifact_size: stored.size_bytes,
    fingerprint, source_sha: sourceSha };
  const chunk = await readRunResultArtifact(env, ownerId, { run_id: runId,
    artifact_id: stored.artifact_id, offset: 0, max_bytes: 8 });
  assert.equal(chunk.machine_state.eof, false);
  assert.equal(chunk.machine_state.next_offset, 8);
  const key = [...objects.keys()][0];
  objects.get(key).bytes[0] ^= 1;
  await assert.rejects(readRunResultArtifact(env, ownerId, { run_id: runId,
    artifact_id: stored.artifact_id, offset: 0, max_bytes: 8 }), /ARTIFACT_CHECKSUM_MISMATCH/);
});

test("run artifact content and chunk limits share one bounded policy", async () => {
  const { env } = storage();
  await assert.rejects(persistRunResultArtifact(env, { runId, ownerId, sourceSha, planFingerprint: fingerprint,
    resultJson: "x".repeat(RUN_ARTIFACT_MAX_BYTES + 1), now: 1_800_000_000 }), /RUN_ARTIFACT_TOO_LARGE/);
  await assert.rejects(readRunResultArtifact(env, ownerId, { run_id: runId,
    artifact_id: "result-json-v1", offset: 0, max_bytes: RUN_ARTIFACT_MAX_BYTES + 1 }), /INVALID_ARGUMENTS/);
});
