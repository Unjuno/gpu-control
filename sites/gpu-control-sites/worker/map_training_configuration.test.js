import assert from "node:assert/strict";
import test from "node:test";
import { mapTrainingConfiguration } from "./map_training_configuration.js";

test("MAP workload settings have one normalized execution configuration", () => {
  assert.deepEqual(mapTrainingConfiguration({
    MAP_TRAINING_SOURCE_SHA: "a".repeat(40),
    MAP_TRAINING_MODAL_IMAGE_ID: "im-Abcdefgh1234",
    MAP_TRAINING_IMAGE_DIGEST: "sha256:" + "b".repeat(64),
    MAP_TRAINING_HOURLY_MICROUSD: "250000",
    MAP_TRAINING_QUOTE_EXPIRES_AT: "1600",
    MAP_TRAINING_RUNTIME_SECONDS: "120",
    MAP_TRAINING_MONTHLY_MICROUSD: "1000000",
  }), {
    source_sha: "a".repeat(40),
    image_id: "im-Abcdefgh1234",
    image_digest: "sha256:" + "b".repeat(64),
    hourly_microusd: 250000,
    quote_expires_at: 1600,
    runtime_seconds: 120,
    monthly_microusd: 1000000,
  });
});

test("missing MAP workload settings remain invalid instead of receiving invented values", () => {
  const config = mapTrainingConfiguration({});
  assert.equal(config.source_sha, undefined);
  assert.equal(Number.isNaN(config.hourly_microusd), true);
  assert.equal(Number.isNaN(config.runtime_seconds), true);
});
