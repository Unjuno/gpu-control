import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { buildGoogleColabExecutionCode } from "./google_colab_execution_code.js";

const manifest = { schema_version: 1, task: "train", entrypoint: "train.py", python_version: "3.11",
  dependencies_lock: "requirements.lock", gpu_profiles: ["T4"],
  outputs: ["metrics.json", "checkpoints/final.pt", "artifacts/result.json"] };

test("Colab execution code pins public source and hash-locked dependencies without embedding credentials", () => {
  const code = buildGoogleColabExecutionCode({ runId: "a".repeat(32), repository: "Owner/Model",
    commit: "b".repeat(40), visibility: "public", manifest, runtimeSeconds: 300, accelerator: "T4" });
  assert.match(code, /https:\/\/github\.com\/owner\/model\.git/);
  assert.match(code, /'fetch', '--depth=1', 'origin', CFG\['commit'\]/);
  assert.match(code, /'--require-hashes'/);
  assert.match(code, /timeout=CFG\['runtime_seconds'\]/);
  assert.match(code, /GPU_CONTROL_RECEIPT:/);
  assert.match(code, /\.receipt\.json/);
  assert.match(code, /nvidia-smi/);
  assert.match(code, /torch\.cuda\.is_available\(\)/);
  assert.match(code, /GPU_SPEC_MISMATCH/);
  assert.match(code, /52428800/);
  assert.match(code, /104857600/);
  assert.doesNotMatch(code, /Bearer |token|secret/i);
  const checked = spawnSync("python3", ["-c", `compile(${JSON.stringify(code)}, '<colab-run>', 'exec')`], { encoding: "utf8" });
  assert.equal(checked.status, 0, checked.stderr);
});

test("Colab execution code rejects mutable, malformed, or overlong plans", () => {
  const valid = { runId: "a".repeat(32), repository: "owner/model", commit: "b".repeat(40), manifest,
    visibility: "public", runtimeSeconds: 300, accelerator: "T4" };
  assert.throws(() => buildGoogleColabExecutionCode({ ...valid, repository: "https://attacker.example/model" }),
    { message: "TRAINING_SOURCE_INVALID" });
  assert.throws(() => buildGoogleColabExecutionCode({ ...valid, commit: "main" }),
    { message: "TRAINING_SOURCE_INVALID" });
  assert.throws(() => buildGoogleColabExecutionCode({ ...valid, runtimeSeconds: 361 }),
    { message: "GOOGLE_COLAB_EXECUTION_PLAN_INVALID" });
  assert.throws(() => buildGoogleColabExecutionCode({ ...valid,
    manifest: { ...manifest, entrypoint: "../outside.py" } }),
  { message: "GOOGLE_COLAB_EXECUTION_PLAN_INVALID" });
  assert.throws(() => buildGoogleColabExecutionCode({ ...valid, accelerator: "H100" }),
    { message: "GOOGLE_COLAB_EXECUTION_PLAN_INVALID" });
  assert.throws(() => buildGoogleColabExecutionCode({ ...valid, visibility: "private" }),
    { message: "GOOGLE_COLAB_EXECUTION_PLAN_INVALID" });
});
