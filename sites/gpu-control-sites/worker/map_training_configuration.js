/** Normalize the immutable MAP workload profile from Worker bindings. */
export function mapTrainingConfiguration(env) {
  return {
    admission_enabled: env.MAP_TRAINING_ADMISSION_ENABLED === "true",
    source_sha: env.MAP_TRAINING_SOURCE_SHA,
    image_id: env.MAP_TRAINING_MODAL_IMAGE_ID,
    image_digest: env.MAP_TRAINING_IMAGE_DIGEST,
    hourly_microusd: Number(env.MAP_TRAINING_HOURLY_MICROUSD),
    quote_expires_at: Number(env.MAP_TRAINING_QUOTE_EXPIRES_AT),
    runtime_seconds: Number(env.MAP_TRAINING_RUNTIME_SECONDS),
    monthly_microusd: Number(env.MAP_TRAINING_MONTHLY_MICROUSD),
  };
}
