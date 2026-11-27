import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

/** Discover the complete static import closure packaged from the Worker entrypoint. */
export function discoverWorkerModules(workerRoot) {
  const root = resolve(workerRoot);
  const entrypoint = join(root, "index.js");
  const runtimeFiles = readdirSync(root)
    .filter((name) => name.endsWith(".js") && !name.endsWith(".test.js"))
    .map((name) => join(root, name));
  const runtimeSet = new Set(runtimeFiles);
  const graph = new Map();

  for (const file of runtimeFiles) {
    const source = readFileSync(file, "utf8");
    const imports = [...source.matchAll(/^\s*import\b[^;]*;/gm)];
    const withoutStaticImports = source.replace(/^\s*import\b[^;]*;/gm, "");
    assert.doesNotMatch(withoutStaticImports, /^\s*import\b/m,
      `${file}: use a static import declaration ending in a semicolon`);
    assert.doesNotMatch(source, /\bimport\s*\(/,
      `${file}: dynamic imports make the dependency graph incomplete`);

    const dependencies = [];
    for (const statement of imports) {
      const match = statement[0].match(/\bfrom\s*["']([^"']+)["']|^\s*import\s*["']([^"']+)["']/s);
      assert.ok(match, `${file}: could not read static import specifier`);
      const specifier = match[1] || match[2];
      assert.ok(specifier.startsWith("."), `${file}: unexpected external Worker import ${specifier}`);
      const dependency = resolve(dirname(file), specifier);
      assert.ok(runtimeSet.has(dependency), `${file}: import is outside the runtime module inventory: ${specifier}`);
      dependencies.push(dependency);
    }
    graph.set(file, dependencies);
  }

  const entry = resolve(entrypoint);
  assert.ok(runtimeSet.has(entry), "Worker runtime is missing index.js");
  const reachable = new Set();
  function visit(file) {
    if (reachable.has(file)) return;
    reachable.add(file);
    for (const dependency of graph.get(file) || []) visit(dependency);
  }
  visit(entry);
  return { entrypoint: entry, graph, runtimeFiles, reachableFiles: [...reachable].sort() };
}
