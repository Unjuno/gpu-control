import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";

const MODAL_GPU_ACCOUNT_EVIDENCE_GPU = "T4";
const MODAL_GPU_ACCOUNT_USAGE_LIMIT_USD = "30.00";

/** One fail-closed interpretation for the live Modal GPU workload gate. */
export function modalGpuWorkloadAdmissionEnabled(env) {
  return env?.MODAL_GPU_WORKLOAD_ADMISSION_ENABLED === "true";
}

/** Read the exact account evidence required by the fixed Modal GPU workload. */
export function readModalGpuProviderEvidence(env, now) {
  return readModalGpuAccountEvidence(env, {
    gpu: MODAL_GPU_ACCOUNT_EVIDENCE_GPU,
    usageLimitUsd: MODAL_GPU_ACCOUNT_USAGE_LIMIT_USD,
    now,
  });
}
