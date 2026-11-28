/** One fail-closed interpretation for the live Modal GPU workload gate. */
export function modalGpuWorkloadAdmissionEnabled(env) {
  return env?.MODAL_GPU_WORKLOAD_ADMISSION_ENABLED === "true";
}
