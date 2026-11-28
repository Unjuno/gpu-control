import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { discoverWorkerModules } from "./worker-module-graph.mjs";

function withWorkerFiles(files, callback) {
  const root = mkdtempSync(join(tmpdir(), "gpu-control-worker-graph-"));
  try {
    for (const [path, source] of Object.entries(files)) {
      const destination = join(root, path);
      mkdirSync(join(destination, ".."), { recursive: true });
      writeFileSync(destination, source);
    }
    return callback(root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test("the Worker graph includes named and wildcard re-export dependencies", () => {
  withWorkerFiles({
    "index.js": 'export { run } from "./facade.js";\n',
    "facade.js": 'export * from "./domain.js";\n',
    "domain.js": "export const run = () => true;\n",
  }, (root) => {
    const { graph, runtimeFiles, reachableFiles } = discoverWorkerModules(root);
    const entrypoint = join(root, "index.js");
    const facade = join(root, "facade.js");
    const domain = join(root, "domain.js");
    assert.deepEqual(graph.get(entrypoint), [facade]);
    assert.deepEqual(graph.get(facade), [domain]);
    assert.equal(reachableFiles.length, runtimeFiles.length);
  });
});

test("the Worker graph rejects re-export declarations without a semicolon", () => {
  withWorkerFiles({
    "index.js": 'export { run } from "./domain.js"\n',
    "domain.js": "export const run = () => true;\n",
  }, (root) => assert.throws(() => discoverWorkerModules(root), /static re-export declaration/));
});
