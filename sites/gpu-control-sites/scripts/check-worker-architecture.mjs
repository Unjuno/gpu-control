import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { discoverWorkerModules } from "./worker-module-graph.mjs";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const workerRoot = join(projectRoot, "worker");
const { graph, runtimeFiles: workerFiles, entrypoint } = discoverWorkerModules(workerRoot);

// ChatGPT's identity header is trusted only at the HTTP transport boundary.
// Domain modules receive an already resolved owner and must not re-interpret
// a platform header or environment allowlist as an identity source.
const platformIdentitySources = workerFiles.filter((file) =>
  file !== entrypoint && /oai-authenticated-user-id|GPU_CONTROL_ALLOWED_USER_IDS/.test(readFileSync(file, "utf8")));
assert.deepEqual(platformIdentitySources, [],
  "ChatGPT platform identity and owner allowlist may only be read by the Worker entrypoint");

const artifactStorageSources = workerFiles.filter((file) =>
  file !== join(workerRoot, "run_artifacts.js") && /\bBUCKET\.(?:get|put|delete)\s*\(/.test(readFileSync(file, "utf8")));
assert.deepEqual(artifactStorageSources, [],
  "R2 run artifact reads, writes, and cleanup must stay inside run_artifacts.js");

for (const [file, dependencies] of graph) {
  assert.ok(workerFiles.includes(file));
  assert.ok(!dependencies.includes(entrypoint), `${file}: domain modules must not import the Worker entrypoint`);
  if (file.endsWith("_contract.js")) {
    const trainingOrchestrator = dependencies.filter((dependency) => dependency.endsWith("/training_plan.js"));
    assert.deepEqual(trainingOrchestrator, [], `${file}: contracts must consume training policy/contracts, not training plan orchestration`);
  }
}

const visiting = new Set();
const visited = new Set();
function visit(file, chain = []) {
  if (visiting.has(file)) {
    const cycle = [...chain, file].map((item) => item.slice(workerRoot.length + 1)).join(" -> ");
    assert.fail(`Worker module cycle: ${cycle}`);
  }
  if (visited.has(file)) return;
  visiting.add(file);
  for (const dependency of graph.get(file) || []) visit(dependency, [...chain, file]);
  visiting.delete(file);
  visited.add(file);
}

for (const file of workerFiles) visit(file);
console.log(`Worker architecture is acyclic across ${workerFiles.length} runtime modules.`);
