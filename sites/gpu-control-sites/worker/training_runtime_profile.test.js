import assert from "node:assert/strict";
import test from "node:test";
import { trainingRuntimeProfileConfigured } from "./training_contract.js";
import { ownerTrainingAdmissionEnabled, ownerTrainingExecutionConfig } from "./training_runtime_profile.js";

test("owner training profile is parsed through one normalized configuration", () => {
  const config = ownerTrainingExecutionConfig({
    OWNER_TRAINING_RUNTIME_IMAGE_ID: "im-Abcdefgh1234",
    OWNER_TRAINING_HOURLY_MICROUSD: "100000",
    OWNER_TRAINING_STAGING_HOURLY_MICROUSD: "25000",
    OWNER_TRAINING_QUOTE_EXPIRES_AT: "1600",
    OWNER_TRAINING_MAX_RUNTIME_SECONDS: "300",
    OWNER_TRAINING_MAX_COST_MICROUSD: "1000000",
    OWNER_TRAINING_MONTHLY_MICROUSD: "30000000",
    MAP_TRAINING_CONTROL_PLANE_SHA: "a".repeat(40),
  });

  assert.deepEqual(config, {
    image_id: "im-Abcdefgh1234",
    hourly_microusd: 100000,
    staging_hourly_microusd: 25000,
    quote_expires_at: 1600,
    max_runtime_seconds: 300,
    max_cost_microusd: 1000000,
    monthly_microusd: 30000000,
    control_plane_sha: "a".repeat(40),
  });
  assert.equal(trainingRuntimeProfileConfigured(config, 1000), true);
});

test("missing owner profile settings remain invalid instead of gaining a runtime fallback", () => {
  const config = ownerTrainingExecutionConfig({});
  assert.equal(Number.isNaN(config.hourly_microusd), true);
  assert.equal(Number.isNaN(config.max_runtime_seconds), true);
  assert.equal(trainingRuntimeProfileConfigured(config, 1000), false);
});

test("owner training admission accepts only the literal enabled value", () => {
  assert.equal(ownerTrainingAdmissionEnabled({ OWNER_TRAINING_ADMISSION_ENABLED: "true" }), true);
  assert.equal(ownerTrainingAdmissionEnabled({ OWNER_TRAINING_ADMISSION_ENABLED: "TRUE" }), false);
  assert.equal(ownerTrainingAdmissionEnabled({}), false);
});
