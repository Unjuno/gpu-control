import { parseTrainingSource } from "./training_source.js";

export const TRAINING_MANIFEST_PATH = ".gpu-control/experiment.json";
const MANIFEST_PATH = TRAINING_MANIFEST_PATH;
const MAX_MANIFEST_BYTES = 8 * 1024;

function validRelativePythonPath(value) {
  return typeof value === "string" && value.length <= 240 && value.endsWith(".py") &&
    !value.startsWith("/") && value.split("/").every((part) =>
      part && part !== "." && part !== ".." && /^[A-Za-z0-9_.-]+$/.test(part));
}

function validManifest(value) {
  const keys = ["dependencies_lock", "entrypoint", "gpu_profiles", "outputs", "python_version", "schema_version", "task"];
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).sort().join(",") !== keys.join(",") || value.schema_version !== 1 ||
      !["train", "evaluate"].includes(value.task) ||
      !validRelativePythonPath(value.entrypoint) ||
      !["3.11", "3.12"].includes(value.python_version) ||
      typeof value.dependencies_lock !== "string" || value.dependencies_lock.length > 240 ||
      value.dependencies_lock.startsWith("/") ||
      !value.dependencies_lock.split("/").every((part) =>
        part && part !== "." && part !== ".." && /^[A-Za-z0-9_.-]+$/.test(part)) ||
      !value.dependencies_lock.endsWith(".lock") ||
      !Array.isArray(value.gpu_profiles) || value.gpu_profiles.length < 1 || value.gpu_profiles.length > 2 ||
      value.gpu_profiles.some((profile) => !["T4", "L4"].includes(profile)) ||
      new Set(value.gpu_profiles).size !== value.gpu_profiles.length ||
      !Array.isArray(value.outputs) || value.outputs.length > 16 ||
      value.outputs.some((path) => typeof path !== "string" || path.length > 240 || path.startsWith("/") ||
        !path.split("/").every((part) => part && part !== "." && part !== ".." && /^[A-Za-z0-9_.*-]+$/.test(part)))) {
    return false;
  }
  return true;
}

function manifestReadiness(manifest, lockfile) {
  const checks = {
    immutable_source: true,
    entrypoint: validRelativePythonPath(manifest.entrypoint),
    supported_python: ["3.11", "3.12"].includes(manifest.python_version),
    dependency_lock_path: typeof manifest.dependencies_lock === "string" && manifest.dependencies_lock.endsWith(".lock"),
    dependency_lock_present_at_commit: Boolean(lockfile),
    supported_gpu_profile: manifest.gpu_profiles.some((profile) => ["T4", "L4"].includes(profile)),
    checkpoint_output: manifest.outputs.some((output) => /(^|\/)(checkpoint|checkpoints)(\/|$)/i.test(output)),
    metrics_output: manifest.outputs.some((output) => /(^|\/)(metrics|metrics\.json)(\/|$)/i.test(output)),
  };
  const missing = Object.entries(checks).filter(([, ok]) => !ok).map(([key]) => key);
  // The current runtime cannot yet build the locked environment, verify its
  // digest, or return bounded artifacts, even if the repository manifest is
  // otherwise compatible.
  missing.push("reviewed_runtime_image", "dependency_environment_build", "artifact_transport", "provider_cleanup_receipt");
  return { checks, missing, ready: false };
}

async function readPublicFile(repository, path, commit, maxBytes, fetchImpl) {
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  const url = new URL(`https://api.github.com/repos/${repository}/contents/${encodedPath}`);
  url.searchParams.set("ref", commit);
  let response;
  try {
    response = await fetchImpl(url.toString(), { method: "GET", redirect: "error",
      headers: { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28" },
      signal: AbortSignal.timeout(5_000) });
  } catch {
    throw new Error("TRAINING_GITHUB_LOOKUP_FAILED");
  }
  const value = await boundedJson(response, maxBytes * 2);
  if (!value || value.type !== "file" || value.path !== path || value.encoding !== "base64" ||
      !Number.isSafeInteger(value.size) || value.size < 1 || value.size > maxBytes ||
      typeof value.content !== "string") throw new Error("TRAINING_SOURCE_FILE_INVALID");
  const encoded = value.content.replace(/\s/g, "");
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) {
    throw new Error("TRAINING_SOURCE_FILE_INVALID");
  }
  let bytes;
  try { bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0)); }
  catch { throw new Error("TRAINING_SOURCE_FILE_INVALID"); }
  if (bytes.byteLength !== value.size || bytes.byteLength > maxBytes) throw new Error("TRAINING_SOURCE_FILE_INVALID");
  return bytes;
}

async function boundedJson(response, maxBytes) {
  if (!response.ok) {
    if (response.status === 404) throw new Error("TRAINING_EXPERIMENT_MANIFEST_NOT_FOUND");
    if (response.status === 403 || response.status === 429) throw new Error("TRAINING_GITHUB_RATE_LIMITED");
    throw new Error("TRAINING_GITHUB_LOOKUP_FAILED");
  }
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) throw new Error("TRAINING_EXPERIMENT_MANIFEST_TOO_LARGE");
  if (!response.body) throw new Error("TRAINING_GITHUB_RESPONSE_INVALID");
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        throw new Error("TRAINING_EXPERIMENT_MANIFEST_TOO_LARGE");
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID"); }
}

export function validateTrainingManifest(value) {
  return validManifest(value);
}

export async function readPublicTrainingContract(repository, commit, fetchImpl = fetch) {
  const source = parseTrainingSource(repository, commit);
  const url = new URL(`https://api.github.com/repos/${source.repository}/contents/${MANIFEST_PATH}`);
  url.searchParams.set("ref", source.commit);
  let response;
  try {
    response = await fetchImpl(url.toString(), { method: "GET", redirect: "error",
      headers: { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28" },
      signal: AbortSignal.timeout(5_000) });
  } catch {
    throw new Error("TRAINING_GITHUB_LOOKUP_FAILED");
  }
  const value = await boundedJson(response, MAX_MANIFEST_BYTES * 2);
  if (Number.isSafeInteger(value?.size) && value.size > MAX_MANIFEST_BYTES) {
    throw new Error("TRAINING_EXPERIMENT_MANIFEST_TOO_LARGE");
  }
  if (!value || value.type !== "file" || value.path !== MANIFEST_PATH ||
      value.encoding !== "base64" || value.size < 2 || value.size > MAX_MANIFEST_BYTES ||
      typeof value.content !== "string") throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID");
  const encoded = value.content.replace(/\s/g, "");
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) {
    throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID");
  }
  let manifestBytes;
  try { manifestBytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0)); }
  catch { throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID"); }
  if (manifestBytes.byteLength !== value.size || manifestBytes.byteLength > MAX_MANIFEST_BYTES) {
    throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID");
  }
  let manifest;
  try { manifest = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(manifestBytes)); }
  catch { throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID"); }
  if (!validManifest(manifest)) throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID");
  let lockBytes;
  try {
    lockBytes = await readPublicFile(source.repository, manifest.dependencies_lock, source.commit, 64 * 1024, fetchImpl);
  } catch (error) {
    if (error?.message === "TRAINING_GITHUB_LOOKUP_FAILED") throw error;
    lockBytes = null;
  }
  const lockSha256 = lockBytes
    ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", lockBytes))]
      .map((byte) => byte.toString(16).padStart(2, "0")).join("") : null;
  const readiness = manifestReadiness(manifest, lockBytes);
  return { repository: source.repository, commit: source.commit, manifest_path: MANIFEST_PATH,
    manifest, manifest_sha256: [...new Uint8Array(await crypto.subtle.digest("SHA-256", manifestBytes))]
      .map((byte) => byte.toString(16).padStart(2, "0")).join(""),
    dependency_lock: lockBytes ? { path: manifest.dependencies_lock, size_bytes: lockBytes.byteLength,
      sha256: lockSha256 } : { path: manifest.dependencies_lock, state: "unavailable" },
    readiness, execution_available: false,
    execution_blocking_reason: "CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED" };
}
