import { readBoundedResponseBytes } from "../../worker/http_response_body.js";
import { validGoogleColabRuntime } from "../../worker/google_colab_mcp_contract.js";
import { sha256Hex } from "../../worker/sha256.js";

export const GOOGLE_COLAB_MAX_FILE_BYTES = 50 * 1024 * 1024;
const FILE_TIMEOUT_MS = 30_000;

function validRelativePath(value) {
  return typeof value === "string" && value.length <= 240 && !value.startsWith("/") &&
    value.split("/").every((part) => part && part !== "." && part !== ".." && /^[A-Za-z0-9_.-]+$/.test(part));
}

function runtimeFileUrl(runtime, relativePath) {
  if (!validGoogleColabRuntime(runtime) || !validRelativePath(relativePath)) {
    throw new Error("GOOGLE_COLAB_RUNTIME_FILE_INVALID");
  }
  const base = new URL(runtime.connectionInfo.url);
  base.pathname = `${base.pathname.replace(/\/$/, "")}/files/${relativePath.split("/").map(encodeURIComponent).join("/")}`;
  return base;
}

/** Retrieve one declared file from a run-owned Colab runtime and verify its immutable receipt. */
export async function readGoogleColabRuntimeFile(runtime, artifact, options = {}) {
  if (!validGoogleColabRuntime(runtime) || options.expectedRuntimeName !== runtime.name) {
    throw new Error("GOOGLE_COLAB_RUNTIME_FILE_INVALID");
  }
  if (!artifact || typeof artifact !== "object" || Array.isArray(artifact) ||
      !validRelativePath(artifact.path) || !Number.isSafeInteger(artifact.size_bytes) ||
      artifact.size_bytes < 1 || artifact.size_bytes > GOOGLE_COLAB_MAX_FILE_BYTES ||
      typeof artifact.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(artifact.sha256)) {
    throw new Error("GOOGLE_COLAB_ARTIFACT_INVALID");
  }
  const url = runtimeFileUrl(runtime, artifact.path);
  const fetchImpl = options.fetchImpl || fetch;
  let response;
  try {
    response = await fetchImpl(url, { method: "GET", redirect: "error", signal: AbortSignal.timeout(FILE_TIMEOUT_MS),
      headers: { "X-Colab-Runtime-Proxy-Token": runtime.connectionInfo.token,
        accept: "application/octet-stream" } });
  } catch { throw new Error("GOOGLE_COLAB_RUNTIME_FILE_UNAVAILABLE"); }
  if (!response.ok) throw new Error("GOOGLE_COLAB_RUNTIME_FILE_HTTP_ERROR");
  const bytes = await readBoundedResponseBytes(response, { maxBytes: artifact.size_bytes,
    tooLargeCode: "GOOGLE_COLAB_ARTIFACT_SIZE_MISMATCH", missingBodyCode: "GOOGLE_COLAB_ARTIFACT_INVALID",
    cancelDeclaredOversize: true });
  if (bytes.byteLength !== artifact.size_bytes || await sha256Hex(bytes) !== artifact.sha256) {
    throw new Error("GOOGLE_COLAB_ARTIFACT_CHECKSUM_MISMATCH");
  }
  return bytes;
}
