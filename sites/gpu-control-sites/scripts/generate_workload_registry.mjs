import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const registry = JSON.parse(readFileSync(`${root}/workloads/registry.json`, "utf8"));
assert.equal(registry.schema_version, 1);
assert.equal(Object.keys(registry.workloads).length, 5);
const ids = Object.values(registry.workloads).map((item) => item.id);
assert.equal(new Set(ids).size, ids.length, "workload ids must be unique");
for (const workload of Object.values(registry.workloads)) {
  assert.match(workload.id, /^[a-z0-9-]+$/);
  assert.match(workload.repository, /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/);
  assert.match(workload.cost_ceiling_usd, /^(?:0|[0-9]+\.[0-9]{2})$/);
  assert.equal(typeof workload.requires_gpu, "boolean");
  if (workload.adapter_manifest) {
    assert.equal(workload.adapter_manifest.provider, workload.provider);
    assert.equal(workload.adapter_manifest.source_repository, workload.repository);
    assert.match(workload.adapter_manifest.source_sha, /^[0-9a-f]{40}$/);
    if (workload.adapter_manifest.image_digest) assert.match(workload.adapter_manifest.image_digest, /^sha256:[0-9a-f]{64}$/);
  }
  if (workload.source_revision) assert.match(workload.source_revision, /^[0-9a-f]{40}$/);
}

const compact = JSON.stringify(registry.workloads);
const js = `// Generated from workloads/registry.json by scripts/generate_workload_registry.mjs.\nexport const WORKLOADS = Object.freeze(${compact});\nexport const WORKLOAD_IDS = Object.freeze(Object.values(WORKLOADS).map((item) => item.id));\n`;
const pyJsonLiteral = JSON.stringify(JSON.stringify(registry.workloads));
const py = `# Generated from workloads/registry.json by scripts/generate_workload_registry.mjs.\nimport json\n\nWORKLOADS = json.loads(${pyJsonLiteral})\n` +
  Object.entries({
    WORKLOAD: "tiny_stories", RUNPOD_WORKLOAD: "runpod_canary", KAGGLE_WORKLOAD: "kaggle_training",
    HF_WORKLOAD: "huggingface_evaluation", MODAL_GPU_WORKLOAD: "modal_gpu_canary",
  }).map(([constant, name]) => `${constant} = WORKLOADS[${JSON.stringify(name)}]["id"]`).join("\n") + "\n";

const outputs = [
  [`${root}/worker/workload_registry.js`, js],
  [`${root}/modal/workload_registry.py`, py],
];
const check = process.argv.includes("--check");
let stale = false;
for (const [path, content] of outputs) {
  let current = "";
  try { current = readFileSync(path, "utf8"); } catch {}
  if (current !== content) {
    stale = true;
    if (!check) writeFileSync(path, content);
  }
}
if (check && stale) {
  console.error("Generated workload registry is stale. Run npm run generate:registry.");
  process.exitCode = 1;
} else if (!check) console.log("Generated Worker and Modal workload registry modules.");
