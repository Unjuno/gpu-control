import { GOOGLE_COLAB_MAX_FILE_BYTES } from "./google_colab_runtime_files.js";

const RECEIPT_PREFIX = "GPU_CONTROL_RECEIPT:";
const MAX_TOTAL_OUTPUT_BYTES = 100 * 1024 * 1024;
const MAX_ARTIFACTS = 16;

/** Parse only the runner's bounded machine receipt; all other output stays untrusted text. */
export function parseGoogleColabExecutionReceipt(stdout, expected) {
  if (typeof stdout !== "string" || new TextEncoder().encode(stdout).byteLength > 64 * 1024 ||
      !expected || typeof expected !== "object" || Array.isArray(expected)) {
    throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
  }
  const lines = stdout.split(/\r?\n/).filter((line) => line.startsWith(RECEIPT_PREFIX));
  if (lines.length !== 1) throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
  let receipt;
  try { receipt = JSON.parse(lines[0].slice(RECEIPT_PREFIX.length)); }
  catch { throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID"); }
  if (!receipt || typeof receipt !== "object" || Array.isArray(receipt) ||
      receipt.run_id !== expected.runId || receipt.repository !== expected.repository ||
      receipt.commit !== expected.commit || !["succeeded", "failed"].includes(receipt.state) ||
      !Number.isSafeInteger(receipt.elapsed_seconds) || receipt.elapsed_seconds < 0 ||
      !Array.isArray(receipt.artifacts) || receipt.artifacts.length > MAX_ARTIFACTS ||
      !(receipt.metrics === null || receipt.metrics && typeof receipt.metrics === "object" && !Array.isArray(receipt.metrics)) ||
      !(receipt.gpu === null || receipt.gpu && typeof receipt.gpu === "object" && !Array.isArray(receipt.gpu)) ||
      !(receipt.exit_code === null || Number.isSafeInteger(receipt.exit_code)) ||
      !(receipt.error_code === null || ["WORKLOAD_TIMEOUT", "SOURCE_OR_DEPENDENCY_COMMAND_FAILED", "COLAB_EXECUTION_FAILED",
        "GPU_NOT_AVAILABLE", "GPU_SPEC_MISMATCH", "METRICS_INVALID", "OUTPUT_LIMIT_EXCEEDED"].includes(receipt.error_code))) {
    throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
  }
  let total = 0;
  const seen = new Set();
  for (const artifact of receipt.artifacts) {
    if (!artifact || typeof artifact !== "object" || Array.isArray(artifact) ||
        typeof artifact.path !== "string" || !expected.outputs?.includes(artifact.path) || seen.has(artifact.path) ||
        !Number.isSafeInteger(artifact.size_bytes) || artifact.size_bytes < 1 ||
        artifact.size_bytes > GOOGLE_COLAB_MAX_FILE_BYTES ||
        typeof artifact.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(artifact.sha256)) {
      throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
    }
    seen.add(artifact.path);
    total += artifact.size_bytes;
    if (total > MAX_TOTAL_OUTPUT_BYTES) throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
  }
  if (receipt.state === "succeeded" &&
      (!receipt.gpu || receipt.gpu.cuda_available !== true || typeof receipt.gpu.name !== "string" ||
       receipt.gpu.name.length > 128 || !Number.isSafeInteger(receipt.gpu.device_count) || receipt.gpu.device_count < 1 ||
       !expected.accelerator || !["T4", "L4"].includes(expected.accelerator) ||
       !receipt.gpu.name.toLowerCase().includes(expected.accelerator.toLowerCase()))) {
    throw new Error("GOOGLE_COLAB_GPU_EVIDENCE_MISSING");
  }
  if (receipt.state === "succeeded" && (!Number.isSafeInteger(receipt.exit_code) || receipt.exit_code !== 0)) {
    throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
  }
  if (receipt.state === "succeeded" && (!receipt.metrics || !seen.has("metrics.json") || receipt.error_code !== null)) {
    throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
  }
  return receipt;
}
