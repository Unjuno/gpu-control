import assert from "node:assert/strict";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { discoverWorkerModules } from "./worker-module-graph.mjs";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const workerRoot = join(projectRoot, "worker");
const { graph, runtimeFiles: workerFiles, entrypoint } = discoverWorkerModules(workerRoot);

for (const [file, dependencies] of graph) {
  assert.ok(workerFiles.includes(file));
  assert.ok(!dependencies.includes(entrypoint), `${file}: domain modules must not import the Worker entrypoint`);
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
