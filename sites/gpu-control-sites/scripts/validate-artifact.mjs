import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../dist/", import.meta.url));
const manifest = JSON.parse(readFileSync(join(root, ".openai/hosting.json"), "utf8"));
assert.equal(manifest.project_id, "appgprj_6af482670c2081919ffe27a6faa0f746");
assert.equal(manifest.d1, "DB");
assert.equal(manifest.r2, "BUCKET");
assert.ok(manifest.capabilities.includes("mcp"));
assert.ok(statSync(join(root, "server/index.js")).size > 0);
const migrations = readdirSync(join(root, ".openai/drizzle"));
assert.ok(migrations.some((name) => name.endsWith(".sql")));
const artifactMigration = readFileSync(join(root, ".openai/drizzle/0001_result_artifacts.sql"), "utf8");
assert.match(artifactMigration, /result_artifact_sha256/);
assert.match(artifactMigration, /result_artifact_size/);
console.log("Site Worker artifact is complete.");
