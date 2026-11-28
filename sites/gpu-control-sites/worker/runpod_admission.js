// Admission and completion-transport policy have one source of truth for
// capabilities, planning, and submission. Provider-specific callers shape the
// response for their own lifecycle stage but must use this decision.
export function runpodAdmissionBlocker(env) {
  if (env.RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED !== "true") {
    return "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED";
  }
  if (env.RUNPOD_WORKLOAD_ADMISSION_ENABLED !== "true") {
    return "RUNPOD_ADMISSION_DISABLED";
  }
  return null;
}
