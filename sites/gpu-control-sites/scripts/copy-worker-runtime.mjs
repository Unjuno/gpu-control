import assert from "node:assert/strict";
import { copyFileSync, mkdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { discoverWorkerModules } from "./worker-module-graph.mjs";

const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const workerRoot = resolve(process.argv[2] || join(projectRoot, "worker"));
const outputRoot = resolve(process.argv[3] || join(projectRoot, "dist/server"));
const { reachableFiles, runtimeFiles } = discoverWorkerModules(workerRoot);
assert.equal(reachableFiles.length, runtimeFiles.length,
  `Unreachable Worker modules: ${runtimeFiles.filter((file) => !reachableFiles.includes(file)).map((file) => basename(file)).join(", ")}`);

mkdirSync(outputRoot, { recursive: true });
for (const source of reachableFiles) copyFileSync(source, join(outputRoot, basename(source)));
console.log(`Copied ${reachableFiles.length} reachable Worker runtime modules.`);
