import assert from "node:assert/strict";
import test from "node:test";
import { parseGoogleColabExecutionReceipt } from "./google_colab_result.js";

const expected = { runId: "a".repeat(32), repository: "owner/model", commit: "b".repeat(40),
  accelerator: "T4", outputs: ["metrics.json", "checkpoints/final.pt"] };
const receipt = { run_id: expected.runId, repository: expected.repository, commit: expected.commit,
  state: "succeeded", exit_code: 0, error_code: null, elapsed_seconds: 13, metrics: { loss: 0.42 },
  gpu: { name: "Tesla T4", nvidia_smi_name: "Tesla T4", cuda_available: true,
    device_count: 1, torch_version: "2.11.0", cuda_version: "13.0" },
  artifacts: [{ path: "metrics.json", size_bytes: 20, sha256: "c".repeat(64) }] };

function stdout(value = receipt) { return "ordinary output is not control data\nGPU_CONTROL_RECEIPT:" + JSON.stringify(value); }

test("Colab execution receipt binds the exact run, source, GPU, outputs and checksums", () => {
  assert.deepEqual(parseGoogleColabExecutionReceipt(stdout(), expected), receipt);
  assert.throws(() => parseGoogleColabExecutionReceipt(stdout({ ...receipt, run_id: "d".repeat(32) }), expected),
    { message: "GOOGLE_COLAB_EXECUTION_RESULT_INVALID" });
  assert.throws(() => parseGoogleColabExecutionReceipt(stdout({ ...receipt, gpu: { ...receipt.gpu,
    cuda_available: false } }), expected), { message: "GOOGLE_COLAB_GPU_EVIDENCE_MISSING" });
  assert.throws(() => parseGoogleColabExecutionReceipt(stdout({ ...receipt,
    artifacts: [{ ...receipt.artifacts[0], path: "unlisted.bin" }] }), expected),
  { message: "GOOGLE_COLAB_EXECUTION_RESULT_INVALID" });
  assert.throws(() => parseGoogleColabExecutionReceipt(stdout() + "\n" + stdout().split("\n").at(-1), expected),
    { message: "GOOGLE_COLAB_EXECUTION_RESULT_INVALID" });
});

test("Colab execution receipt rejects output hashes, sizes, and GPU models that do not match the plan", () => {
  assert.throws(() => parseGoogleColabExecutionReceipt(stdout({ ...receipt,
    artifacts: [{ ...receipt.artifacts[0], sha256: "bad" }] }), expected),
  { message: "GOOGLE_COLAB_EXECUTION_RESULT_INVALID" });
  assert.throws(() => parseGoogleColabExecutionReceipt(stdout({ ...receipt, gpu: { ...receipt.gpu,
    name: "Tesla L4" } }), expected), { message: "GOOGLE_COLAB_GPU_EVIDENCE_MISSING" });
});
