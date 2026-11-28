import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const registry = JSON.parse(readFileSync(`${root}/workloads/registry.json`, "utf8"));
const providerCatalog = JSON.parse(readFileSync(`${root}/workloads/provider-catalog.json`, "utf8"));
assert.equal(registry.schema_version, 1);
assert.equal(providerCatalog.schema_version, 1);
assert.ok(providerCatalog.providers && typeof providerCatalog.providers === "object");
assert.ok(providerCatalog.routes && typeof providerCatalog.routes === "object");
for (const [providerId, provider] of Object.entries(providerCatalog.providers)) {
  assert.match(providerId, /^[a-z][a-z0-9_]*$/);
  assert.equal(provider.budget_provider === null || provider.budget_provider === providerId, true);
  assert.ok(["usage_billed", "included_quota"].includes(provider.billing_model));
  assert.equal(typeof provider.credit_eligible, "boolean");
  if (provider.budget_provider === null) assert.equal(provider.quota_limited, true);
  if (provider.billing_model === "included_quota") assert.equal(provider.paid_fallback_allowed, false);
}
for (const [routeId, route] of Object.entries(providerCatalog.routes)) {
  assert.match(routeId, /^[a-z][a-z0-9_]*$/);
  assert.ok(providerCatalog.providers[route.provider], `${routeId}: unknown provider ${route.provider}`);
  assert.equal(typeof route.requires_gpu, "boolean");
  assert.equal(typeof route.adapter_hosted, "boolean");
}
for (const workload of Object.values(registry.workloads)) {
  const route = providerCatalog.routes[workload.provider];
  assert.ok(route, `${workload.id}: unknown provider route ${workload.provider}`);
  assert.equal(workload.requires_gpu, route.requires_gpu, `${workload.id}: GPU capability disagrees with ${workload.provider}`);
  assert.equal(Boolean(workload.adapter_manifest), route.adapter_hosted,
    `${workload.id}: adapter manifest requirement disagrees with ${workload.provider}`);
}
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
const providerJs = `// Generated from workloads/provider-catalog.json by scripts/generate_workload_registry.mjs.\nexport const PROVIDER_CATALOG = Object.freeze(${JSON.stringify(providerCatalog)});\nexport const PROVIDERS = Object.freeze(Object.fromEntries(Object.entries(PROVIDER_CATALOG.providers).map(([id, provider]) => [id, Object.freeze({ id, ...provider })])));\nexport const PROVIDER_ROUTES = Object.freeze(Object.fromEntries(Object.entries(PROVIDER_CATALOG.routes).map(([id, route]) => [id, Object.freeze({ id, ...route })])));\nexport const PROVIDER_ROUTE_IDS = Object.freeze(Object.keys(PROVIDER_ROUTES));\nexport const PROVIDER_BUDGET_IDS = Object.freeze([...new Set(Object.values(PROVIDERS).map((provider) => provider.budget_provider).filter(Boolean))]);\nexport const FREE_PROVIDER_BUDGET_IDS = Object.freeze(Object.values(PROVIDERS).filter((provider) => provider.billing_model === "included_quota" && provider.budget_provider).map((provider) => provider.budget_provider));\n`;
const pyJsonLiteral = JSON.stringify(JSON.stringify(registry.workloads));
const py = `# Generated from workloads/registry.json by scripts/generate_workload_registry.mjs.\nimport json\n\nWORKLOADS = json.loads(${pyJsonLiteral})\n` +
  Object.entries({
    WORKLOAD: "tiny_stories", RUNPOD_WORKLOAD: "runpod_canary", KAGGLE_WORKLOAD: "kaggle_training",
    HF_WORKLOAD: "huggingface_evaluation", MODAL_GPU_WORKLOAD: "modal_gpu_canary",
  }).map(([constant, name]) => `${constant} = WORKLOADS[${JSON.stringify(name)}]["id"]`).join("\n") + "\n";

const outputs = [
  [`${root}/worker/workload_registry.js`, js],
  [`${root}/worker/provider_catalog.js`, providerJs],
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
