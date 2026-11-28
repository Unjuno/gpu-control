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

// The browser's exact-plan confirmation is one HTTP/security boundary. Keep
// challenge issuance and consumption out of the transport composition root.
const trainingAuthorizationBoundary = join(workerRoot, "training_authorization_routes.js");
const confirmationChallengeSources = workerFiles.filter((file) =>
  file !== trainingAuthorizationBoundary && /authorization_challenges/.test(readFileSync(file, "utf8")));
assert.deepEqual(confirmationChallengeSources, [],
  "Browser authorization challenge issuance and consumption must stay inside training_authorization_routes.js");

// Owner-selected runtime profile values and its literal admission flag are
// normalized in one module. The live gate stays semantically separate from
// profile validity; callers must not re-parse either setting.
function modulesReadingBindingsOutside(boundary, bindings) {
  const directRead = new RegExp(`\\benv\\??\\.(?:${bindings.join("|")})\\b`);
  return workerFiles.filter((file) =>
    file !== boundary && directRead.test(readFileSync(file, "utf8")));
}

const trainingRuntimeProfileBoundary = join(workerRoot, "training_runtime_profile.js");
const ownerRuntimeProfileBindings = ["OWNER_TRAINING_RUNTIME_IMAGE_ID", "OWNER_TRAINING_HOURLY_MICROUSD",
  "OWNER_TRAINING_STAGING_HOURLY_MICROUSD", "OWNER_TRAINING_QUOTE_EXPIRES_AT",
  "OWNER_TRAINING_MAX_RUNTIME_SECONDS", "OWNER_TRAINING_MAX_COST_MICROUSD",
  "OWNER_TRAINING_MONTHLY_MICROUSD", "OWNER_TRAINING_ADMISSION_ENABLED"];
const ownerRuntimeProfileSources = modulesReadingBindingsOutside(trainingRuntimeProfileBoundary,
  ownerRuntimeProfileBindings);
assert.deepEqual(ownerRuntimeProfileSources, [],
  "Owner training runtime profile values may only be read by training_runtime_profile.js");

// The reviewed MAP workload profile has one environment parser as well. The
// live admission decision remains separate from profile validity, and the
// shared control-plane signing key has its own identity/security concern.
const mapTrainingConfigBoundary = join(workerRoot, "map_training_configuration.js");
const mapTrainingConfigBindings = ["MAP_TRAINING_SOURCE_SHA", "MAP_TRAINING_MODAL_IMAGE_ID",
  "MAP_TRAINING_IMAGE_DIGEST", "MAP_TRAINING_HOURLY_MICROUSD", "MAP_TRAINING_QUOTE_EXPIRES_AT",
  "MAP_TRAINING_RUNTIME_SECONDS", "MAP_TRAINING_MONTHLY_MICROUSD", "MAP_TRAINING_ADMISSION_ENABLED"];
const mapTrainingConfigSources = modulesReadingBindingsOutside(mapTrainingConfigBoundary,
  mapTrainingConfigBindings);
assert.deepEqual(mapTrainingConfigSources, [],
  "MAP training source, image, quote and runtime settings may only be read by map_training_configuration.js");

const trainingSecurityConfigBoundary = join(workerRoot, "training_security_configuration.js");
const trainingSecurityConfigSources = modulesReadingBindingsOutside(trainingSecurityConfigBoundary,
  ["MAP_TRAINING_CONTROL_PLANE_SHA"]);
assert.deepEqual(trainingSecurityConfigSources, [],
  "The shared training authorization identity may only be read by training_security_configuration.js");

const artifactStorageSources = workerFiles.filter((file) =>
  file !== join(workerRoot, "run_artifacts.js") && /\bBUCKET\.(?:get|put|delete)\s*\(/.test(readFileSync(file, "utf8")));
assert.deepEqual(artifactStorageSources, [],
  "R2 run artifact reads, writes, and cleanup must stay inside run_artifacts.js");

const boundedResponseReader = join(workerRoot, "http_response_body.js");
const rawResponseReaders = workerFiles.filter((file) =>
  file !== boundedResponseReader && /response\.body\??\.getReader\s*\(/.test(readFileSync(file, "utf8")));
assert.deepEqual(rawResponseReaders, [],
  "External HTTP response streams must use http_response_body.js for bounded byte collection");

const trainingUseCases = new Set(["training_preview.js", "training_prepare.js", "training_submit.js"]);
const forbiddenTrainingDependencies = new Map([
  ["training_preview.js", new Set(["training_prepare.js", "training_submit.js"])],
  ["training_prepare.js", new Set(["training_submit.js"])],
]);

for (const [file, dependencies] of graph) {
  assert.ok(workerFiles.includes(file));
  assert.ok(!dependencies.includes(entrypoint), `${file}: domain modules must not import the Worker entrypoint`);
  if (file.endsWith("_contract.js")) {
    const useCases = dependencies.filter((dependency) => trainingUseCases.has(dependency.split("/").at(-1)));
    assert.deepEqual(useCases, [], `${file}: contracts must consume training policy/contracts, not training use cases`);
  }
  const forbidden = forbiddenTrainingDependencies.get(file.split("/").at(-1));
  if (forbidden) {
    const dependenciesByUseCase = dependencies.map((dependency) => dependency.split("/").at(-1));
    assert.deepEqual(dependenciesByUseCase.filter((dependency) => forbidden.has(dependency)), [],
      `${file}: training use-case dependencies must flow from preview to prepare to submit`);
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
