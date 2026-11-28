import { WORKLOADS } from "./workload_registry.js";

// One provider policy owns the values used by plan pricing and job submission.
export const RUNPOD_RUNTIME_SECONDS = WORKLOADS.runpod_canary.runtime_seconds;
export const RUNPOD_EXECUTION_TIMEOUT_SECONDS = RUNPOD_RUNTIME_SECONDS;
export const RUNPOD_JOB_TTL_SECONDS = 300;
export const RUNPOD_WORKER_IDLE_TIMEOUT_SECONDS = 5;
export const RUNPOD_DEFAULT_INITIALIZATION_SECONDS = 420;
export const RUNPOD_ESTIMATED_BILLABLE_SECONDS = RUNPOD_DEFAULT_INITIALIZATION_SECONDS +
  RUNPOD_JOB_TTL_SECONDS + RUNPOD_WORKER_IDLE_TIMEOUT_SECONDS;
export const RUNPOD_COST_ESTIMATE_ASSUMPTIONS =
  `RunPod documented default initTimeout ${RUNPOD_DEFAULT_INITIALIZATION_SECONDS}s + job TTL ${RUNPOD_JOB_TTL_SECONDS}s + configured idle ${RUNPOD_WORKER_IDLE_TIMEOUT_SECONDS}s; endpoint overrides and automatic retries may increase charges`;
