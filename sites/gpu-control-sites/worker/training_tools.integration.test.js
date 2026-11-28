import assert from "node:assert/strict";
import test from "node:test";
import { handleTrainingTool } from "./training_tools.js";

test("missing owner-training adapter journal stays uncertain and cannot resubmit", async () => {
  const runId = "a".repeat(32);
  const fingerprint = "b".repeat(64);
  const plan = { execution_kind: "owner_selected_python", run_id: runId };
  const row = {
    fingerprint,
    plan_json: JSON.stringify(plan),
    expires_at: Math.floor(Date.now() / 1000) + 600,
    cancelled_at: null,
    dispatch_claimed_at: Math.floor(Date.now() / 1000) - 1,
    dispatch_rejection: null,
    cleanup_confirmed_at: null,
  };
  const env = { MAP_TRAINING_ADMISSION_ENABLED: "true", DB: {
    prepare(sql) {
      return { bind() { return { first: async () => {
        if (sql.includes("FROM training_plans")) return row;
        if (sql.includes("FROM training_authorizations")) return null;
        throw new Error(`unexpected query: ${sql}`);
      }, run: async () => ({ meta: { changes: 0 } }) }; } };
    },
  } };
  const delegatedCalls = [];
  const delegate = async (_env, _owner, tool, args) => {
    delegatedCalls.push({ tool, args });
    return { state: "not_found" };
  };
  const services = { env, owner: "owner", delegate, isConfigured: () => true,
    getSourceToken: async () => null };

  const status = await handleTrainingTool("training_status", { run_id: runId }, services);
  assert.equal(status.machine_state.state, "uncertain");
  assert.equal(status.machine_state.provider_resource_created, "unknown");
  assert.equal(status.machine_state.cleanup_state, "unknown");
  assert.equal(status.blocking_reason, "SUBMISSION_OUTCOME_UNCONFIRMED");
  assert.match(status.human_summary, /二重実行を避けて同じrunの照合/);
  assert.deepEqual(status.next_allowed_actions, ["training_status"]);

  const cancel = await handleTrainingTool("training_cancel", { run_id: runId }, services);
  assert.equal(cancel.machine_state.state, "uncertain");
  assert.equal(cancel.machine_state.provider_resource_created, "unknown");
  assert.equal(cancel.machine_state.cleanup_state, "unknown");
  assert.equal(cancel.blocking_reason, "SUBMISSION_OUTCOME_UNCONFIRMED");

  const repeatedSubmit = await handleTrainingTool("training_submit", {
    run_id: runId, plan_fingerprint: fingerprint, approved_plan: plan,
  }, services);
  assert.equal(repeatedSubmit.machine_state.state, "dispatching");
  assert.deepEqual(delegatedCalls, [
    { tool: "training_status", args: { run_id: runId, plan_fingerprint: fingerprint } },
    { tool: "training_cancel", args: { run_id: runId, plan_fingerprint: fingerprint } },
  ]);
});
