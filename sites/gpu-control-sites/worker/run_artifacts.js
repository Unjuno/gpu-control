const RUN_ARTIFACT_ID = "result-json-v1";
const RUN_ARTIFACT_MAX_BYTES = 8 * 1024;

async function sha256Bytes(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

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

export async function persistRunResultArtifact(env, { runId, ownerId, sourceSha, planFingerprint, resultJson, now }) {
  if (!env?.DB || !env?.BUCKET || typeof env.BUCKET.put !== "function" ||
      !/^[0-9a-f]{32}$/.test(runId || "") || typeof ownerId !== "string" || ownerId.length < 1 || ownerId.length > 256 ||
      !/^[0-9a-f]{40}$/.test(sourceSha || "") || !/^[0-9a-f]{64}$/.test(planFingerprint || "") ||
      !Number.isSafeInteger(now)) throw new Error("RUN_ARTIFACT_STORAGE_UNAVAILABLE");
  const bytes = runArtifactBytes(resultJson);
  if (bytes.byteLength < 1 || bytes.byteLength > RUN_ARTIFACT_MAX_BYTES) throw new Error("RUN_ARTIFACT_TOO_LARGE");
  const digest = await sha256Bytes(bytes);
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
  if (bytes.length !== row.result_artifact_size || await sha256Bytes(bytes) !== row.result_artifact_sha256) {
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
