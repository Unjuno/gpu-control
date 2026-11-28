/** Colab-specific runtime admission. Undefined is closed by default. */
export function googleColabAdmissionEnabled(env) {
  return env?.GOOGLE_COLAB_WORKLOAD_ADMISSION_ENABLED === "true";
}
