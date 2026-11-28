import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { discoverWorkerModules } from "./worker-module-graph.mjs";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const workerRoot = join(projectRoot, "worker");
const { graph, runtimeFiles: workerFiles, entrypoint } = discoverWorkerModules(workerRoot);

// ChatGPT's identity header and allowlist are interpreted only in the request
// authentication boundary. Other modules may ask its exported helpers, but
// must not read the raw identity header or allowlist.
const requestAuthBoundary = join(workerRoot, "mcp_request_auth.js");
const platformIdentitySources = workerFiles.filter((file) =>
  file !== requestAuthBoundary &&
    /oai-authenticated-user-id|GPU_CONTROL_ALLOWED_USER_IDS/.test(readFileSync(file, "utf8")));
assert.deepEqual(platformIdentitySources, [],
  "ChatGPT platform identity and owner allowlist may only be interpreted by mcp_request_auth.js");

// Owner-selected runtime profile values are normalized in one module. Admission
// remains a separate live gate, but image, pricing, quote, runtime and budget
// inputs must not be re-parsed by capabilities or lifecycle callers.
const trainingRuntimeProfileBoundary = join(workerRoot, "training_runtime_profile.js");
const ownerRuntimeProfileSources = workerFiles.filter((file) =>
  file !== trainingRuntimeProfileBoundary &&
    /\benv\??\.(?:OWNER_TRAINING_RUNTIME_IMAGE_ID|OWNER_TRAINING_HOURLY_MICROUSD|OWNER_TRAINING_STAGING_HOURLY_MICROUSD|OWNER_TRAINING_QUOTE_EXPIRES_AT|OWNER_TRAINING_MAX_RUNTIME_SECONDS|OWNER_TRAINING_MAX_COST_MICROUSD|OWNER_TRAINING_MONTHLY_MICROUSD)\b/.test(readFileSync(file, "utf8")));
assert.deepEqual(ownerRuntimeProfileSources, [],
  "Owner training runtime profile values may only be read by training_runtime_profile.js");

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
