import { parseTrainingSource } from "./training_source.js";
import { sha256Hex } from "./sha256.js";
import { readBoundedResponseBytes } from "./http_response_body.js";

export const TRAINING_MANIFEST_PATH = ".gpu-control/experiment.json";
const MANIFEST_PATH = TRAINING_MANIFEST_PATH;
const MAX_MANIFEST_BYTES = 8 * 1024;

function validRelativePythonPath(value) {
  return typeof value === "string" && value.length <= 240 && value.endsWith(".py") &&
    !value.startsWith("/") && value.split("/").every((part) =>
      part && part !== "." && part !== ".." && /^[A-Za-z0-9_.-]+$/.test(part));
}

function validOutputPath(value) {
  if (typeof value !== "string" || value.length > 240 || value.startsWith("/") || value.includes("*")) return false;
  const parts = value.split("/");
  if (parts.some((part) => !part || part === "." || part === ".." || !/^[A-Za-z0-9_.-]+$/.test(part))) return false;
  return value === "metrics.json" || /(^|\/)(checkpoint|checkpoints)(\/|$)/i.test(value) ||
    value.startsWith("artifacts/") && parts.length >= 2;
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
      new Set(value.outputs).size !== value.outputs.length || value.outputs.some((path) => !validOutputPath(path))) {
    return false;
  }
  return true;
}

function validateDependencyLock(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength < 1 || bytes.byteLength > 64 * 1024) return false;
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { return false; }
  const packages = new Set();
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const [requirement, ...hashes] = line.split(/\s+/);
    const match = /^([A-Za-z0-9][A-Za-z0-9_.-]{0,127})==([A-Za-z0-9][A-Za-z0-9.!+_-]{0,127})$/.exec(requirement || "");
    if (!match || hashes.length < 1 || hashes.some((value) => !/^--hash=sha256:[0-9a-f]{64}$/.test(value))) return false;
    const normalized = match[1].replace(/[-_.]+/g, "-").toLowerCase();
    if (packages.has(normalized)) return false;
    packages.add(normalized);
    if (packages.size > 128) return false;
  }
  return packages.size > 0;
}

export function trainingRuntimeProfileConfigured(executionConfig, now = Math.floor(Date.now() / 1000)) {
  return Boolean(executionConfig &&
    /^im-[A-Za-z0-9]{8,128}$/.test(executionConfig.image_id || "") &&
    Number.isSafeInteger(executionConfig.hourly_microusd) && executionConfig.hourly_microusd > 0 &&
    executionConfig.hourly_microusd <= 1_000_000_000 &&
    Number.isSafeInteger(executionConfig.staging_hourly_microusd) &&
    executionConfig.staging_hourly_microusd > 0 && executionConfig.staging_hourly_microusd <= 1_000_000_000 &&
    Number.isSafeInteger(executionConfig.quote_expires_at) && executionConfig.quote_expires_at > now &&
    executionConfig.quote_expires_at <= now + 30 * 86400 &&
    Number.isSafeInteger(executionConfig.max_runtime_seconds) && executionConfig.max_runtime_seconds >= 120 &&
    executionConfig.max_runtime_seconds <= 3000 &&
    Number.isSafeInteger(executionConfig.max_cost_microusd) && executionConfig.max_cost_microusd >= 1 &&
    executionConfig.max_cost_microusd <= 1_000_000 &&
    Number.isSafeInteger(executionConfig.monthly_microusd) && executionConfig.monthly_microusd > 0 &&
    executionConfig.monthly_microusd <= 30_000_000);
}

export async function trainingRuntimeProfileFingerprint(executionConfig, now = Math.floor(Date.now() / 1000)) {
  if (!trainingRuntimeProfileConfigured(executionConfig, now) ||
      !trainingControlPlaneConfigured(executionConfig.control_plane_sha)) return null;
  const fields = ["image_id", "hourly_microusd", "staging_hourly_microusd", "quote_expires_at",
    "max_runtime_seconds", "max_cost_microusd", "monthly_microusd", "control_plane_sha"];
  const canonical = JSON.stringify(fields.map((field) => executionConfig[field]));
  return sha256Hex(canonical);
}

export function trainingControlPlaneConfigured(controlPlaneSha) {
  return typeof controlPlaneSha === "string" && /^[0-9a-f]{40}$/.test(controlPlaneSha);
}

function sourceManifestReadiness(manifest, lockfile) {
  const checks = {
    immutable_source: true,
    entrypoint: validRelativePythonPath(manifest.entrypoint),
    supported_python: ["3.11", "3.12"].includes(manifest.python_version),
    dependency_lock_path: typeof manifest.dependencies_lock === "string" && manifest.dependencies_lock.endsWith(".lock"),
    dependency_lock_present_at_commit: Boolean(lockfile),
    dependency_lock_has_exact_versions_and_hashes: validateDependencyLock(lockfile),
    supported_gpu_profile: manifest.gpu_profiles.some((profile) => ["T4", "L4"].includes(profile)),
    checkpoint_output: manifest.outputs.some((output) => /(^|\/)(checkpoint|checkpoints)(\/|$)/i.test(output)),
    metrics_output: manifest.outputs.includes("metrics.json"),
  };
  const missing = Object.entries(checks).filter(([, ok]) => !ok).map(([key]) => key);
  return { checks, missing, ready: missing.length === 0 };
}

function manifestReadiness(manifest, lockfile, executionConfig) {
  const source = sourceManifestReadiness(manifest, lockfile);
  const checks = source.checks;
  const missing = [...source.missing];
  const runtimeConfigured = trainingRuntimeProfileConfigured(executionConfig);
  if (!runtimeConfigured) missing.push("reviewed_runtime_image_and_provider_quote");
  return { checks, missing, ready: missing.length === 0 };
}

async function readPublicFile(repository, path, commit, maxBytes, fetchImpl, installationToken = null) {
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  const url = new URL(`https://api.github.com/repos/${repository}/contents/${encodedPath}`);
  url.searchParams.set("ref", commit);
  let response;
  try {
    response = await fetchImpl(url.toString(), { method: "GET", redirect: "error",
      headers: { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28",
        ...(installationToken ? { authorization: `Bearer ${installationToken}` } : {}) },
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
  const bytes = await readBoundedResponseBytes(response, {
    maxBytes, tooLargeCode: "TRAINING_EXPERIMENT_MANIFEST_TOO_LARGE",
    missingBodyCode: "TRAINING_GITHUB_RESPONSE_INVALID",
  });
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new Error("TRAINING_EXPERIMENT_MANIFEST_INVALID"); }
}

export function validateTrainingManifest(value) {
  return validManifest(value);
}

export async function readTrainingSourceContract(repository, commit, fetchImpl = fetch, installationToken = null) {
  const source = parseTrainingSource(repository, commit);
  const url = new URL(`https://api.github.com/repos/${source.repository}/contents/${MANIFEST_PATH}`);
  url.searchParams.set("ref", source.commit);
  let response;
  try {
    response = await fetchImpl(url.toString(), { method: "GET", redirect: "error",
      headers: { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28",
        ...(installationToken ? { authorization: `Bearer ${installationToken}` } : {}) },
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
    lockBytes = await readPublicFile(source.repository, manifest.dependencies_lock, source.commit,
      64 * 1024, fetchImpl, installationToken);
  } catch (error) {
    if (error?.message === "TRAINING_GITHUB_LOOKUP_FAILED") throw error;
    lockBytes = null;
  }
  const lockSha256 = lockBytes ? await sha256Hex(lockBytes) : null;
  const sourceReadiness = sourceManifestReadiness(manifest, lockBytes);
  return { repository: source.repository, commit: source.commit, manifest_path: MANIFEST_PATH,
    manifest, manifest_sha256: await sha256Hex(manifestBytes),
    dependency_lock: lockBytes ? { path: manifest.dependencies_lock, size_bytes: lockBytes.byteLength,
      sha256: lockSha256, bytes: lockBytes } : { path: manifest.dependencies_lock, state: "unavailable" },
    source_readiness: sourceReadiness };
}

/** Add a provider runtime profile to the source-only manifest contract. */
export async function readPublicTrainingContract(repository, commit, fetchImpl = fetch, installationToken = null,
  executionConfig = null) {
  const sourceContract = await readTrainingSourceContract(repository, commit, fetchImpl, installationToken);
  const readiness = manifestReadiness(sourceContract.manifest, sourceContract.dependency_lock.bytes || null, executionConfig);
  const { bytes: _lockBytes, ...dependencyLock } = sourceContract.dependency_lock;
  return { ...sourceContract, dependency_lock: dependencyLock,
    readiness, execution_available: readiness.ready,
    execution_blocking_reason: readiness.ready ? null :
      readiness.missing.length === 1 && readiness.missing[0] === "reviewed_runtime_image_and_provider_quote"
        ? "CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED" : "TRAINING_MANIFEST_OR_LOCK_INVALID" };
}
