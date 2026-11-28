import { GOOGLE_COLAB_WORKLOAD } from "./google_colab_plan.js";
import { GOOGLE_COLAB_MAX_ARTIFACT_BYTES } from "./google_colab_execution_limits.js";
import { readGoogleColabRuntimeFile } from "./google_colab_runtime_files.js";
import { readVerifiedRunArtifactObjectChunk, putVerifiedRunArtifactObject } from "./run_artifacts.js";

function artifactResult(status, summary, runId, state, actions, blocker) {
  return { schema_version: 2, status, human_summary: summary,
    machine_state: { run_id: runId, provider: "google_colab", workload: GOOGLE_COLAB_WORKLOAD,
      state, cleanup_state: "unknown" }, next_allowed_actions: actions, blocking_reason: blocker };
}

/** Download, verify and persist the artifacts owned by one Colab execution. */
export async function persistGoogleColabArtifacts(env, owner, runId, fingerprint, runtime, receipt, fetchImpl, now) {
  if (!receipt.artifacts.length) return [];
  const saved = [];
  for (let index = 0; index < receipt.artifacts.length; index++) {
    const artifact = receipt.artifacts[index];
    const artifactId = `artifact-${String(index + 1).padStart(2, "0")}`;
    const bytes = await readGoogleColabRuntimeFile(runtime, artifact,
      { expectedRuntimeName: runtime.name, fetchImpl });
    if (bytes.byteLength > GOOGLE_COLAB_MAX_ARTIFACT_BYTES) throw new Error("GOOGLE_COLAB_ARTIFACT_TOO_LARGE");
    const key = `colab/runs/${runId}/${fingerprint}/${artifactId}`;
    await putVerifiedRunArtifactObject(env, { key, bytes, metadata: { run_id: runId, owner_id: owner,
      plan_fingerprint: fingerprint, artifact_id: artifactId, sha256: artifact.sha256 } });
    await env.DB.prepare(`INSERT OR IGNORE INTO google_colab_run_artifacts
      (run_id, owner_id, plan_fingerprint, artifact_id, path, object_key, sha256, size_bytes, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`).bind(runId, owner, fingerprint, artifactId, artifact.path,
      key, artifact.sha256, bytes.byteLength, now).run();
    saved.push({ artifact_id: artifactId, path: artifact.path, sha256: artifact.sha256,
      size_bytes: bytes.byteLength });
  }
  return saved;
}

function base64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

/** Return one owner-scoped artifact chunk after validating its ledger and full-object digest. */
export async function readGoogleColabArtifact(env, owner, args) {
  const row = await env.DB.prepare(`SELECT a.run_id, a.artifact_id, a.object_key, a.sha256, a.size_bytes,
      p.fingerprint, p.provider_state FROM google_colab_run_artifacts a
    JOIN gateway_delegated_plans p ON p.id=a.run_id AND p.owner_id=a.owner_id AND p.fingerprint=a.plan_fingerprint
    WHERE a.owner_id=? AND a.run_id=? AND a.artifact_id=?`)
    .bind(owner, args.run_id, args.artifact_id).first();
  if (!row) {
    const colabRun = await env.DB.prepare(`SELECT id FROM gateway_delegated_plans
      WHERE owner_id=? AND id=? AND workload=?`).bind(owner, args.run_id, GOOGLE_COLAB_WORKLOAD).first();
    return colabRun ? artifactResult("blocked", "このColab runには該当artifactがありません。",
      args.run_id, "unknown", ["experiment_result"], "ARTIFACT_NOT_READY") : null;
  }
  if (row.provider_state !== "succeeded") {
    return artifactResult("blocked", "Colab artifactはまだ取得できません。", args.run_id,
      row.provider_state || "unknown", ["experiment_status"], "ARTIFACT_NOT_READY");
  }
  const chunk = await readVerifiedRunArtifactObjectChunk(env, { key: row.object_key,
    expected: { run_id: args.run_id, owner_id: owner, plan_fingerprint: row.fingerprint,
      artifact_id: row.artifact_id, sha256: row.sha256, size_bytes: row.size_bytes },
    offset: args.offset, maxBytes: args.max_bytes });
  return { schema_version: 2, status: "ok", human_summary: "Colab artifact chunk retrieved and checksum verified.",
    machine_state: { run_id: args.run_id, artifact_id: row.artifact_id, sha256: row.sha256,
      size_bytes: chunk.size_bytes, offset: args.offset, next_offset: chunk.next_offset, eof: chunk.eof,
      encoding: "base64", data: base64(chunk.bytes) },
    next_allowed_actions: [], blocking_reason: null };
}
