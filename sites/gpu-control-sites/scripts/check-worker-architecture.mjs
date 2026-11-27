import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const workerRoot = join(projectRoot, "worker");
const workerFiles = readdirSync(workerRoot)
  .filter((name) => name.endsWith(".js") && !name.endsWith(".test.js"))
  .map((name) => join(workerRoot, name));
const entrypoint = join(workerRoot, "index.js");
const graph = new Map();

for (const file of workerFiles) {
  const source = readFileSync(file, "utf8");
  const imports = [...source.matchAll(/^\s*import\b[^;]*;/gm)];
  const withoutStaticImports = source.replace(/^\s*import\b[^;]*;/gm, "");
  assert.doesNotMatch(withoutStaticImports, /^\s*import\b/m,
    `${file}: use a static import declaration ending in a semicolon`);
  assert.doesNotMatch(source, /\bimport\s*\(/,
    `${file}: dynamic imports make the dependency graph incomplete`);

  const dependencies = [];
  for (const [statement] of imports) {
    const match = statement.match(/\bfrom\s*["']([^"']+)["']|^\s*import\s*["']([^"']+)["']/s);
    assert.ok(match, `${file}: could not read static import specifier`);
    const specifier = match[1] || match[2];
    assert.ok(specifier.startsWith("."), `${file}: unexpected external Worker import ${specifier}`);
    const dependency = resolve(dirname(file), specifier);
    assert.ok(workerFiles.includes(dependency), `${file}: import is outside the runtime module inventory: ${specifier}`);
    assert.notEqual(dependency, entrypoint, `${file}: domain modules must not import the Worker entrypoint`);
    dependencies.push(dependency);
  }
  graph.set(file, dependencies);
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
