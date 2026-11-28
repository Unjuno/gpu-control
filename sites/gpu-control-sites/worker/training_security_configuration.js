/** Read the shared, immutable training authorization identity from bindings. */
export function trainingControlPlaneSha(env) {
  return env.MAP_TRAINING_CONTROL_PLANE_SHA;
}
