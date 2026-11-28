import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { authorizeTrainingMcpSubmit, getTrainingAuthorization } from "./training_authorization.js";

test("native MCP submit confirmation is bound to one exact owner plan", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    for (const file of ["0022_training_registrations.sql", "0023_training_plans.sql",
      "0024_training_plan_cancellation.sql", "0025_training_submission_claim.sql",
      "0026_training_authorizations.sql", "0029_training_authorization_evidence.sql"]) {
      db.exec(readFileSync(new URL(`../drizzle/${file}`, import.meta.url), "utf8"));
    }
    const now = 1_800_000_000;
    const owner = "chat-owner";
    const runId = "a".repeat(32);
    const fingerprint = "b".repeat(64);
    const controlPlaneSha = "c".repeat(40);
    const plan = { execution_kind: "owner_selected_python", repository: "owner/model",
      commit: "d".repeat(40), image_digest: "im-Abcdefgh1234", provider: "modal",
      provider_resource_id: "gpu-control-provider-adapter/owner_training", gpu_count: 1,
      runtime_seconds: 300, max_cost_microusd: 100000, control_plane_sha: controlPlaneSha };
    db.prepare(`INSERT INTO training_registrations (id, owner_id, repository, source_sha, created_at)
      VALUES (?, ?, ?, ?, ?)`).run("e".repeat(32), owner, plan.repository, plan.commit, now);
    db.prepare(`INSERT INTO training_plans
      (id, owner_id, registration_id, idempotency_key, fingerprint, plan_json, created_at, expires_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(runId, owner, "e".repeat(32), "intent-key-123456", fingerprint, JSON.stringify(plan), now, now + 600);
    const bridge = { prepare(sql) { return { bind(...values) { return {
      first: async () => db.prepare(sql).get(...values),
    }; } }; } };

    assert.equal(await authorizeTrainingMcpSubmit(bridge, owner, runId, fingerprint, controlPlaneSha, now), true);
    const first = await getTrainingAuthorization(bridge, owner, runId, fingerprint);
    assert.equal(first.authorization_source, "chatgpt_mcp_write_confirmation");
    assert.equal(first.authorized_by, owner);
    assert.equal(first.target_repository, plan.repository);
    assert.equal(first.target_sha, plan.commit);
    assert.equal(first.control_plane_sha, controlPlaneSha);
    assert.equal(first.max_cost_microusd, plan.max_cost_microusd);
    assert.equal(first.consumed_at, null);
    assert.equal(await authorizeTrainingMcpSubmit(bridge, owner, runId, fingerprint, controlPlaneSha, now + 1), false);

    db.prepare("UPDATE training_authorizations SET authorized_at=NULL, expires_at=? WHERE plan_id=?").run(now, runId);
    assert.equal(await authorizeTrainingMcpSubmit(bridge, owner, runId, fingerprint, controlPlaneSha, now + 2), true);
    const renewed = await getTrainingAuthorization(bridge, owner, runId, fingerprint);
    assert.notEqual(renewed.authorization_id, first.authorization_id);
    assert.equal(await authorizeTrainingMcpSubmit(bridge, "other-owner", runId, fingerprint, controlPlaneSha, now + 3), false);
    assert.equal(await authorizeTrainingMcpSubmit(bridge, owner, runId, fingerprint, "f".repeat(40), now + 3), false);

    const mapRunId = "1".repeat(32);
    const mapFingerprint = "2".repeat(64);
    const mapPlan = { execution_kind: "map_training", control_plane_sha: controlPlaneSha,
      repository: "unjuno/model-as-a-paper", commit: "3".repeat(40), image_digest: "im-Abcdefgh1234",
      provider: "modal", provider_resource_id: "gpu-control-map-training/train_map",
      gpu_count: 1, runtime_seconds: 120, max_cost_microusd: 100_000 };
    db.prepare(`INSERT INTO training_plans
      (id, owner_id, registration_id, idempotency_key, fingerprint, plan_json, created_at, expires_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(mapRunId, owner, "e".repeat(32), "map-intent-key-1234", mapFingerprint,
        JSON.stringify(mapPlan), now, now + 600);
    assert.equal(await authorizeTrainingMcpSubmit(bridge, owner, mapRunId, mapFingerprint, controlPlaneSha, now), true);
    const mapAuthorization = await getTrainingAuthorization(bridge, owner, mapRunId, mapFingerprint);
    assert.equal(mapAuthorization.authorization_source, "chatgpt_mcp_write_confirmation");
    assert.equal(mapAuthorization.target_repository, mapPlan.repository);
    assert.equal(mapAuthorization.target_sha, mapPlan.commit);
    assert.equal(mapAuthorization.provider_resource_id, mapPlan.provider_resource_id);
    assert.equal(await authorizeTrainingMcpSubmit(bridge, owner, mapRunId, mapFingerprint, controlPlaneSha, now + 1), false);
  } finally {
    db.close();
  }
});
