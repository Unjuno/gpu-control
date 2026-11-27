import { parseTrainingSource } from "./training_source.js";

const MANIFEST_PATH = ".gpu-control/experiment.json";
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
  return { repository: source.repository, commit: source.commit, manifest_path: MANIFEST_PATH,
    manifest, execution_available: false,
    execution_blocking_reason: "CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED" };
}
