import { trainingControlPlaneSha } from "./training_security_configuration.js";

/** Resolve the owner-selected Modal runtime profile shared by inspection and planning. */
export function ownerTrainingExecutionConfig(env) {
  return {
    image_id: env.OWNER_TRAINING_RUNTIME_IMAGE_ID,
    hourly_microusd: Number(env.OWNER_TRAINING_HOURLY_MICROUSD),
    staging_hourly_microusd: Number(env.OWNER_TRAINING_STAGING_HOURLY_MICROUSD),
    quote_expires_at: Number(env.OWNER_TRAINING_QUOTE_EXPIRES_AT),
    max_runtime_seconds: Number(env.OWNER_TRAINING_MAX_RUNTIME_SECONDS),
    max_cost_microusd: Number(env.OWNER_TRAINING_MAX_COST_MICROUSD),
    monthly_microusd: Number(env.OWNER_TRAINING_MONTHLY_MICROUSD),
    control_plane_sha: trainingControlPlaneSha(env),
  };
}

/** Resolve the independent live admission gate without treating other values as truthy. */
export function ownerTrainingAdmissionEnabled(env) {
  return env.OWNER_TRAINING_ADMISSION_ENABLED === "true";
}
