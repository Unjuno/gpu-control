import assert from "node:assert/strict";
import test from "node:test";
import { trainingControlPlaneSha } from "./training_security_configuration.js";

test("the shared training control-plane identity is read without reinterpretation", () => {
  const sha = "a".repeat(40);
  assert.equal(trainingControlPlaneSha({ MAP_TRAINING_CONTROL_PLANE_SHA: sha }), sha);
  assert.equal(trainingControlPlaneSha({}), undefined);
});
