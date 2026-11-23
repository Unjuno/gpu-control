import assert from "node:assert/strict";
import test from "node:test";
import { verifyRunpodCompletion } from "./runpod_completion.js";

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}
function hex(bytes) { return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join(""); }
function marker(name, value) { return `${name}${Buffer.from(canonical(value)).toString("base64")}`; }

test("authenticates one exact Runpod GPU canary result", async () => {
  const key = new Uint8Array(32).fill(7);
  const expected = { keyId: "a".repeat(32), nonce: "b".repeat(64), planFingerprint: "c".repeat(64),
    sourceSha: "d".repeat(40), imageDigest: `sha256:${"e".repeat(64)}`,
    executionName: `gpu-control-${"f".repeat(12)}` };
  const result = { test: "cuda-driver-canary-v1", gpu_used: true, device_count: 1, device_name: "NVIDIA GPU",
    compute_capability: "8.9", total_vram_bytes: 100, free_vram_bytes: 50, provider: "runpod_gpu",
    source_sha: expected.sourceSha, image_digest: expected.imageDigest, execution_name: expected.executionName,
    elapsed_wall_seconds: 1.25 };
  const resultBytes = new TextEncoder().encode(canonical(result));
  const resultSha256 = hex(new Uint8Array(await crypto.subtle.digest("SHA-256", resultBytes)));
  const unsigned = { schema_version: 3, key_id: expected.keyId, nonce: expected.nonce,
    plan_fingerprint: expected.planFingerprint, execution_name: expected.executionName,
    source_sha: expected.sourceSha, image_digest: expected.imageDigest,
    result_sha256: resultSha256, process_exit_code: 0 };
  const hmacKey = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac_sha256 = hex(new Uint8Array(await crypto.subtle.sign("HMAC", hmacKey,
    new TextEncoder().encode(canonical(unsigned)))));
  const lines = [marker("GPU_CONTROL_RESULT_JSON_V1:", result),
    marker("GPU_CONTROL_COMPLETION_JSON_V3:", { ...unsigned, mac_sha256 })];
  const verified = await verifyRunpodCompletion(lines, key, expected);
  assert.equal(verified.result.gpu_used, true);
  lines[1] = lines[1].replace(/.$/, lines[1].endsWith("A") ? "B" : "A");
  await assert.rejects(verifyRunpodCompletion(lines, key, expected));
});
