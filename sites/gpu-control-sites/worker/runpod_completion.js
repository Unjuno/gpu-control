import { canonicalJson } from "./canonical_json.js";
import { sha256Hex } from "./sha256.js";

const RESULT_MARKER = "GPU_CONTROL_RESULT_JSON_V1:";
const COMPLETION_MARKER = "GPU_CONTROL_COMPLETION_JSON_V3:";
const HEX_32 = /^[0-9a-f]{32}$/;
const HEX_64 = /^[0-9a-f]{64}$/;
const SOURCE_SHA = /^[0-9a-f]{40}$/;
const IMAGE_DIGEST = /^sha256:[0-9a-f]{64}$/;

export class RunpodCompletionError extends Error {
  constructor(code) { super(code); this.name = "RunpodCompletionError"; this.code = code; }
}

function canonical(value) {
  try { return canonicalJson(value, "RUNPOD_COMPLETION_INVALID"); }
  catch { throw new RunpodCompletionError("RUNPOD_COMPLETION_INVALID"); }
}

function decodeMarker(lines, marker) {
  const matches = lines.filter((line) => typeof line === "string" && line.startsWith(marker));
  if (matches.length !== 1) throw new RunpodCompletionError("RUNPOD_COMPLETION_MARKER_INVALID");
  const encoded = matches[0].slice(marker.length);
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded) || encoded.length > 24 * 1024) {
    throw new RunpodCompletionError("RUNPOD_COMPLETION_MARKER_INVALID");
  }
  let bytes;
  try { bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0)); }
  catch { throw new RunpodCompletionError("RUNPOD_COMPLETION_MARKER_INVALID"); }
  let value;
  try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new RunpodCompletionError("RUNPOD_COMPLETION_JSON_INVALID"); }
  if (!value || typeof value !== "object" || Array.isArray(value) || canonical(value) !== new TextDecoder().decode(bytes)) {
    throw new RunpodCompletionError("RUNPOD_COMPLETION_JSON_INVALID");
  }
  return { value, bytes };
}

function hex(bytes) {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}

function validateResult(result, expected) {
  const keys = ["compute_capability", "device_count", "device_name", "elapsed_wall_seconds", "execution_name",
    "free_vram_bytes", "gpu_used", "image_digest", "provider", "source_sha", "test", "total_vram_bytes"];
  if (Object.keys(result).sort().join(",") !== keys.sort().join(",") || result.test !== "cuda-driver-canary-v1" ||
      result.gpu_used !== true || result.device_count !== 1 || result.provider !== "runpod_gpu" ||
      result.source_sha !== expected.sourceSha || result.image_digest !== expected.imageDigest ||
      result.execution_name !== expected.executionName || typeof result.device_name !== "string" ||
      result.device_name.length < 1 || result.device_name.length > 256 ||
      typeof result.compute_capability !== "string" || !/^[0-9]{1,2}\.[0-9]{1,2}$/.test(result.compute_capability) ||
      !Number.isSafeInteger(result.total_vram_bytes) || result.total_vram_bytes < 1 ||
      !Number.isSafeInteger(result.free_vram_bytes) || result.free_vram_bytes < 0 ||
      result.free_vram_bytes > result.total_vram_bytes || typeof result.elapsed_wall_seconds !== "number" ||
      !Number.isFinite(result.elapsed_wall_seconds) || result.elapsed_wall_seconds < 0 || result.elapsed_wall_seconds > 30) {
    throw new RunpodCompletionError("RUNPOD_RESULT_INVALID");
  }
}

export async function verifyRunpodCompletion(lines, completionKeyBytes, expected) {
  if (!Array.isArray(lines) || lines.length > 5000 || !(completionKeyBytes instanceof Uint8Array) ||
      completionKeyBytes.length !== 32 || !expected || !HEX_32.test(expected.keyId) ||
      !HEX_64.test(expected.nonce) || !HEX_64.test(expected.planFingerprint) ||
      !SOURCE_SHA.test(expected.sourceSha) || !IMAGE_DIGEST.test(expected.imageDigest) ||
      typeof expected.executionName !== "string" || !/^gpu-control-[0-9a-f]{12}$/.test(expected.executionName)) {
    throw new RunpodCompletionError("RUNPOD_COMPLETION_EXPECTATION_INVALID");
  }
  const resultMarker = decodeMarker(lines, RESULT_MARKER);
  const completionMarker = decodeMarker(lines, COMPLETION_MARKER);
  const completion = completionMarker.value;
  const completionKeys = ["execution_name", "image_digest", "key_id", "mac_sha256", "nonce",
    "plan_fingerprint", "process_exit_code", "result_sha256", "schema_version", "source_sha"];
  if (Object.keys(completion).sort().join(",") !== completionKeys.sort().join(",") ||
      completion.schema_version !== 3 || completion.key_id !== expected.keyId || completion.nonce !== expected.nonce ||
      completion.plan_fingerprint !== expected.planFingerprint || completion.execution_name !== expected.executionName ||
      completion.source_sha !== expected.sourceSha || completion.image_digest !== expected.imageDigest ||
      completion.process_exit_code !== 0 || !HEX_64.test(completion.result_sha256) || !HEX_64.test(completion.mac_sha256) ||
      completion.result_sha256 !== await sha256Hex(resultMarker.bytes)) {
    throw new RunpodCompletionError("RUNPOD_COMPLETION_IDENTITY_MISMATCH");
  }
  const { mac_sha256: suppliedMac, ...unsigned } = completion;
  const key = await crypto.subtle.importKey("raw", completionKeyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const actualMac = hex(new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(canonical(unsigned)))));
  if (actualMac !== suppliedMac) throw new RunpodCompletionError("RUNPOD_COMPLETION_AUTHENTICATION_FAILED");
  validateResult(resultMarker.value, expected);
  return { result: resultMarker.value, completion, resultSha256: completion.result_sha256 };
}
