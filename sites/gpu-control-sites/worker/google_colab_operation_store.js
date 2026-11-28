import { canonicalJson } from "./canonical_json.js";

const STATES = new Set(["runtime_create_pending", "runtime_ready", "session_create_pending",
  "execution_pending", "execution_complete", "cleanup_pending", "terminal"]);
const TRANSITIONS = {
  runtime_create_pending: new Set(["runtime_ready", "cleanup_pending", "terminal"]),
  runtime_ready: new Set(["session_create_pending", "cleanup_pending"]),
  session_create_pending: new Set(["execution_pending", "cleanup_pending"]),
  execution_pending: new Set(["execution_pending", "execution_complete", "cleanup_pending"]),
  execution_complete: new Set(["execution_pending", "cleanup_pending"]),
  cleanup_pending: new Set(["terminal"]),
  terminal: new Set(),
};

function validIdentity(owner, runId, fingerprint) {
  return typeof owner === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/.test(owner) &&
    /^[0-9a-f]{32}$/.test(runId || "") && /^[0-9a-f]{64}$/.test(fingerprint || "");
}

function validUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

/** Create the durable operation before the idempotent Google create_runtime call. */
export async function createGoogleColabOperation(db, { owner, runId, fingerprint, runtimeRequestId, now }) {
  if (!db || !validIdentity(owner, runId, fingerprint) || !validUuid(runtimeRequestId) || !Number.isSafeInteger(now)) {
    throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  }
  await db.prepare(`INSERT OR IGNORE INTO google_colab_run_operations
    (run_id, owner_id, plan_fingerprint, state, runtime_request_id, updated_at)
    SELECT p.id, p.owner_id, p.fingerprint, 'runtime_create_pending', ?, ?
    FROM gateway_delegated_plans p WHERE p.owner_id=? AND p.id=? AND p.fingerprint=?
      AND p.state='prepared' AND p.cancelled_at IS NULL AND p.expires_at>?`)
    .bind(runtimeRequestId, now, owner, runId, fingerprint, now).run();
  const row = await readGoogleColabOperation(db, owner, runId, fingerprint);
  if (!row || row.runtime_request_id !== runtimeRequestId) throw new Error("GOOGLE_COLAB_OPERATION_NOT_CREATED");
  return row;
}

/** Owner- and fingerprint-scoped operation read; never return another run's state. */
export async function readGoogleColabOperation(db, owner, runId, fingerprint) {
  if (!db || !validIdentity(owner, runId, fingerprint)) throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  return db.prepare(`SELECT run_id, owner_id, plan_fingerprint, state, runtime_request_id,
      execution_id, runtime_name, session_name, connection_ciphertext, connection_iv,
      execution_code_sha256, execution_result_json, updated_at
    FROM google_colab_run_operations WHERE owner_id=? AND run_id=? AND plan_fingerprint=?`)
    .bind(owner, runId, fingerprint).first();
}

/** Compare-and-set one lifecycle step while preserving stable retry identities. */
export async function transitionGoogleColabOperation(db, input) {
  const { owner, runId, fingerprint, fromState, toState, now } = input || {};
  if (!db || !validIdentity(owner, runId, fingerprint) || !STATES.has(fromState) ||
      !TRANSITIONS[fromState]?.has(toState) || !Number.isSafeInteger(now)) {
    throw new Error("GOOGLE_COLAB_OPERATION_INVALID_TRANSITION");
  }
  const allowed = new Set(["execution_id", "runtime_name", "session_name", "connection_ciphertext",
    "connection_iv", "execution_code_sha256", "execution_result_json"]);
  const patch = input.patch || {};
  if (!patch || typeof patch !== "object" || Array.isArray(patch) || Object.keys(patch).some((key) => !allowed.has(key))) {
    throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  }
  if (patch.execution_id !== undefined && !validUuid(patch.execution_id)) throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  if (patch.runtime_name !== undefined && !/^runtimes\/[a-z][a-z0-9-]{0,62}$/.test(patch.runtime_name)) throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  if (patch.session_name !== undefined && !/^runtimes\/[a-z][a-z0-9-]{0,62}\/sessions\/[a-z][a-z0-9-]{0,62}$/.test(patch.session_name)) throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  if (patch.execution_code_sha256 !== undefined && !/^[0-9a-f]{64}$/.test(patch.execution_code_sha256)) throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  if (patch.execution_result_json !== undefined) {
    const encoded = canonicalJson(patch.execution_result_json);
    if (new TextEncoder().encode(encoded).byteLength > 64 * 1024) throw new Error("GOOGLE_COLAB_OPERATION_RESULT_TOO_LARGE");
    patch.execution_result_json = encoded;
  }
  if (toState === "execution_pending" &&
      (!validUuid(patch.execution_id) || !/^[0-9a-f]{64}$/.test(patch.execution_code_sha256 || ""))) {
    throw new Error("GOOGLE_COLAB_OPERATION_INVALID");
  }
  if (fromState === "execution_pending" && toState === "execution_pending") {
    const current = await readGoogleColabOperation(db, owner, runId, fingerprint);
    if (current?.state !== fromState || current.execution_id !== patch.execution_id ||
        current.execution_code_sha256 !== patch.execution_code_sha256) return false;
  }
  const columns = Object.keys(patch);
  const assignments = ["state=?", "updated_at=?", ...columns.map((column) => `${column}=?`)].join(", ");
  const bindings = [toState, now, ...columns.map((column) => patch[column]), owner, runId, fingerprint, fromState,
    patch.runtime_name ?? null, patch.session_name ?? null];
  const result = await db.prepare(`UPDATE google_colab_run_operations SET ${assignments}
    WHERE owner_id=? AND run_id=? AND plan_fingerprint=? AND state=?
      AND (runtime_name IS NULL OR runtime_name=COALESCE(?, runtime_name))
      AND (session_name IS NULL OR session_name=COALESCE(?, session_name))`).bind(...bindings).run();
  return (result?.meta?.changes ?? result?.changes ?? 0) === 1;
}
