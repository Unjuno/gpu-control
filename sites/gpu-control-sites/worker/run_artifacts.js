import { sha256Hex } from "./sha256.js";
import { GOOGLE_COLAB_MAX_ARTIFACT_BYTES } from "./google_colab_execution_limits.js";
import { MAX_EXPERIMENT_ARTIFACT_CHUNK_BYTES } from "./artifact_transfer_policy.js";

const RUN_ARTIFACT_ID = "result-json-v1";
const RUN_ARTIFACT_MAX_BYTES = 8 * 1024;

function base64(bytes) {
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}

function artifactKey(runId, digest, artifactId = RUN_ARTIFACT_ID) {
  return `runs/${runId}/${digest}/${artifactId}`;
}

export function runArtifactBytes(resultJson) {
  if (typeof resultJson !== "string") throw new Error("RUN_ARTIFACT_CONTENT_INVALID");
  return new TextEncoder().encode(resultJson);
}

/** Shared immutable R2 write boundary for provider-owned run artifacts. */
export async function putVerifiedRunArtifactObject(env, { key, bytes, metadata }) {
  if (!env?.BUCKET || typeof env.BUCKET.put !== "function" || !(bytes instanceof Uint8Array) ||
      bytes.byteLength < 1 || bytes.byteLength > GOOGLE_COLAB_MAX_ARTIFACT_BYTES ||
      typeof key !== "string" || !/^colab\/runs\/[0-9a-f]{32}\/[0-9a-f]{64}\/artifact-[0-9]{2}$/.test(key) ||
      !metadata || typeof metadata !== "object" || Array.isArray(metadata) ||
      !/^[0-9a-f]{32}$/.test(metadata.run_id || "") || typeof metadata.owner_id !== "string" ||
      !/^[0-9a-f]{64}$/.test(metadata.plan_fingerprint || "") ||
      !/^artifact-[0-9]{2}$/.test(metadata.artifact_id || "") ||
      !/^[0-9a-f]{64}$/.test(metadata.sha256 || "") || await sha256Hex(bytes) !== metadata.sha256) {
    throw new Error("RUN_ARTIFACT_OBJECT_INVALID");
  }
  await env.BUCKET.put(key, bytes, { customMetadata: { run_id: metadata.run_id, owner_id: metadata.owner_id,
    plan_fingerprint: metadata.plan_fingerprint, artifact_id: metadata.artifact_id, sha256: metadata.sha256 } });
}

/** Bounded chunk read with owner/plan metadata binding and a full-object checksum check. */
export async function readVerifiedRunArtifactObjectChunk(env, { key, expected, offset, maxBytes }) {
  if (!env?.BUCKET || typeof env.BUCKET.get !== "function" ||
      typeof key !== "string" || !/^colab\/runs\/[0-9a-f]{32}\/[0-9a-f]{64}\/artifact-[0-9]{2}$/.test(key) ||
      !expected || typeof expected !== "object" || Array.isArray(expected) ||
      !Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(maxBytes) || maxBytes < 1 ||
      maxBytes > MAX_EXPERIMENT_ARTIFACT_CHUNK_BYTES ||
      !Number.isSafeInteger(expected.size_bytes) || expected.size_bytes < 1 ||
      expected.size_bytes > GOOGLE_COLAB_MAX_ARTIFACT_BYTES || !/^[0-9a-f]{64}$/.test(expected.sha256 || "")) {
    throw new Error("RUN_ARTIFACT_OBJECT_INVALID");
  }
  const object = await env.BUCKET.get(key);
  if (!object || object.size !== expected.size_bytes || object.customMetadata?.run_id !== expected.run_id ||
      object.customMetadata?.owner_id !== expected.owner_id ||
      object.customMetadata?.plan_fingerprint !== expected.plan_fingerprint ||
      object.customMetadata?.artifact_id !== expected.artifact_id || object.customMetadata?.sha256 !== expected.sha256) {
    throw new Error("ARTIFACT_METADATA_MISMATCH");
  }
  const bytes = new Uint8Array(await object.arrayBuffer());
  if (bytes.byteLength !== expected.size_bytes || await sha256Hex(bytes) !== expected.sha256) {
    throw new Error("ARTIFACT_CHECKSUM_MISMATCH");
  }
  if (offset > bytes.byteLength) throw new Error("ARTIFACT_OFFSET_OUT_OF_RANGE");
  const end = Math.min(bytes.byteLength, offset + maxBytes);
  return { bytes: bytes.subarray(offset, end), size_bytes: bytes.byteLength, next_offset: end,
    eof: end === bytes.byteLength };
}

export async function persistRunResultArtifact(env, { runId, ownerId, sourceSha, planFingerprint, resultJson, now }) {
  if (!env?.DB || !env?.BUCKET || typeof env.BUCKET.put !== "function" ||
      !/^[0-9a-f]{32}$/.test(runId || "") || typeof ownerId !== "string" || ownerId.length < 1 || ownerId.length > 256 ||
      !/^[0-9a-f]{40}$/.test(sourceSha || "") || !/^[0-9a-f]{64}$/.test(planFingerprint || "") ||
      !Number.isSafeInteger(now)) throw new Error("RUN_ARTIFACT_STORAGE_UNAVAILABLE");
  const bytes = runArtifactBytes(resultJson);
  if (bytes.byteLength < 1 || bytes.byteLength > RUN_ARTIFACT_MAX_BYTES) throw new Error("RUN_ARTIFACT_TOO_LARGE");
  const digest = await sha256Hex(bytes);
  const key = artifactKey(runId, digest);
  await env.BUCKET.put(key, bytes, { customMetadata: {
    run_id: runId, sha256: digest, plan_fingerprint: planFingerprint, source_sha: sourceSha,
  } });
  const finalized = await env.DB.prepare(`UPDATE runs SET state='succeeded', result_json=?, result_artifact_id=?, result_artifact_sha256=?,
      result_artifact_size=?, failure_code=NULL, cleanup_state='confirmed', updated_at=?
    WHERE id=? AND owner_id=? AND state IN ('queued','running') AND cancel_requested=0`)
    .bind(resultJson, RUN_ARTIFACT_ID, digest, bytes.byteLength, now, runId, ownerId).run();
  if (finalized?.meta?.changes === 1) return { artifact_id: RUN_ARTIFACT_ID, sha256: digest, size_bytes: bytes.byteLength };

  // Cancellation can win after the immutable object write but before D1
  // finalization. Delete only after a read proves success did not win.
  const latest = await env.DB.prepare("SELECT state, cancel_requested FROM runs WHERE id=? AND owner_id=?")
    .bind(runId, ownerId).first();
  if (latest && latest.state !== "succeeded" && (latest.state === "cancelled" || latest.cancel_requested === 1)) {
    await env.BUCKET.delete(key);
  }
  return null;
}

export async function readRunResultArtifact(env, ownerId, args) {
  if (!env?.BUCKET || typeof env.BUCKET.get !== "function") return {
    schema_version: 2, status: "blocked", human_summary: "Artifact storage is not configured.",
    machine_state: { run_id: args.run_id }, next_allowed_actions: ["experiment_status"],
    blocking_reason: "ARTIFACT_STORAGE_NOT_CONFIGURED",
  };
  if (!Number.isSafeInteger(args.offset) || args.offset < 0 || !Number.isSafeInteger(args.max_bytes) ||
      args.max_bytes < 1 || args.max_bytes > RUN_ARTIFACT_MAX_BYTES) throw new Error("INVALID_ARGUMENTS");
  const row = await env.DB.prepare(`SELECT r.id, r.state, r.result_artifact_id, r.result_artifact_sha256, r.result_artifact_size,
      p.fingerprint, p.source_sha
    FROM runs r JOIN plans p ON p.id=r.plan_id WHERE r.id = ? AND r.owner_id = ?`)
    .bind(args.run_id, ownerId).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  if (row.state !== "succeeded" || typeof row.result_artifact_id !== "string" ||
      typeof row.result_artifact_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(row.result_artifact_sha256) ||
      !Number.isSafeInteger(row.result_artifact_size) || row.result_artifact_size < 1 ||
      row.result_artifact_size > RUN_ARTIFACT_MAX_BYTES) {
    return { schema_version: 2, status: "blocked", human_summary: "Artifact is not ready for this run.",
      machine_state: { run_id: args.run_id, state: row.state }, next_allowed_actions: ["experiment_status"],
      blocking_reason: "ARTIFACT_NOT_READY" };
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(row.result_artifact_id) ||
      row.result_artifact_id !== args.artifact_id) return { schema_version: 2, status: "blocked",
    human_summary: "Artifact is not ready for this run.", machine_state: { run_id: args.run_id, state: row.state },
    next_allowed_actions: ["experiment_status"], blocking_reason: "ARTIFACT_NOT_READY" };
  const object = await env.BUCKET.get(artifactKey(args.run_id, row.result_artifact_sha256, row.result_artifact_id));
  if (!object || object.size !== row.result_artifact_size || object.customMetadata?.run_id !== args.run_id ||
      object.customMetadata?.sha256 !== row.result_artifact_sha256 ||
      object.customMetadata?.plan_fingerprint !== row.fingerprint || object.customMetadata?.source_sha !== row.source_sha) {
    throw new Error("ARTIFACT_METADATA_MISMATCH");
  }
  const bytes = new Uint8Array(await object.arrayBuffer());
  if (bytes.length !== row.result_artifact_size || await sha256Hex(bytes) !== row.result_artifact_sha256) {
    throw new Error("ARTIFACT_CHECKSUM_MISMATCH");
  }
  if (args.offset > bytes.length) throw new Error("ARTIFACT_OFFSET_OUT_OF_RANGE");
  const end = Math.min(bytes.length, args.offset + args.max_bytes);
  return { schema_version: 2, status: "ok", human_summary: "Artifact chunk retrieved and verified.",
    machine_state: { run_id: args.run_id, artifact_id: row.result_artifact_id, sha256: row.result_artifact_sha256,
      size_bytes: bytes.length, offset: args.offset, next_offset: end, eof: end === bytes.length,
      encoding: "base64", data: base64(bytes.subarray(args.offset, end)) },
    next_allowed_actions: [], blocking_reason: null };
}

export { RUN_ARTIFACT_ID, RUN_ARTIFACT_MAX_BYTES };
