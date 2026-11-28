import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../dist/", import.meta.url));
const sourceHostingManifest = fileURLToPath(new URL("../.openai/hosting.json", import.meta.url));
const sourceMigrations = fileURLToPath(new URL("../drizzle/", import.meta.url));
const artifactHostingManifest = join(root, ".openai/hosting.json");
assert.deepEqual(
  readFileSync(artifactHostingManifest),
  readFileSync(sourceHostingManifest),
  "built artifact hosting manifest must match its source bytes",
);
JSON.parse(readFileSync(artifactHostingManifest, "utf8"));
assert.ok(statSync(join(root, "server/index.js")).size > 0);
assert.ok(statSync(join(root, "server/provider_adapter_client.js")).size > 0);
assert.ok(statSync(join(root, "server/github_app_connection.js")).size > 0);
assert.ok(statSync(join(root, "server/provider_account_lease.js")).size > 0);
assert.ok(statSync(join(root, "server/runpod_provider.js")).size > 0);
assert.ok(statSync(join(root, "server/runpod_secret.js")).size > 0);
assert.ok(statSync(join(root, "server/workload_registry.js")).size > 0);
assert.ok(statSync(join(root, "server/training_contract.js")).size > 0);
assert.ok(statSync(join(root, "server/provider_budget_policy.js")).size > 0);
assert.ok(statSync(join(root, "server/training_inspection.js")).size > 0);
assert.ok(statSync(join(root, "server/training_tools.js")).size > 0);
const sourceMigrationNames = readdirSync(sourceMigrations)
  .filter((name) => name.endsWith(".sql"))
  .sort();
const artifactMigrationsRoot = join(root, ".openai/drizzle");
const artifactMigrationNames = readdirSync(artifactMigrationsRoot)
  .filter((name) => name.endsWith(".sql"))
  .sort();
assert.ok(sourceMigrationNames.length > 0, "source migration history must not be empty");
assert.deepEqual(artifactMigrationNames, sourceMigrationNames,
  "built artifact must include exactly the source D1 migration files");
for (const name of sourceMigrationNames) {
  assert.deepEqual(
    readFileSync(join(artifactMigrationsRoot, name)),
    readFileSync(join(sourceMigrations, name)),
    `built artifact migration ${name} must match its source bytes`,
  );
}
const worker = await import(new URL("../dist/server/index.js", import.meta.url));
assert.equal(typeof worker.default.fetch, "function");
console.log("Site Worker artifact is complete.");
