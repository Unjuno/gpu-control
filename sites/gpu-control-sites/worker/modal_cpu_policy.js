import { WORKLOADS } from "./workload_registry.js";

/** One fail-closed interpretation for the live Modal CPU execution gate. */
export function modalCpuAdmissionEnabled(env) {
  return env?.CPU_WORKLOAD_ADMISSION_ENABLED === "true";
}

export const MODAL_MAX_RUNTIME_SECONDS = WORKLOADS.tiny_stories.runtime_seconds;
export const MODAL_SANDBOX_CPU_LIMIT_CORES = 1;
export const MODAL_SANDBOX_MEMORY_LIMIT_MIB = 512;
export const MODAL_SANDBOX_RESOURCES = Object.freeze({
  cpu_request_physical_cores: MODAL_SANDBOX_CPU_LIMIT_CORES,
  cpu_limit_physical_cores: MODAL_SANDBOX_CPU_LIMIT_CORES,
  memory_request_mib: MODAL_SANDBOX_MEMORY_LIMIT_MIB,
  memory_limit_mib: MODAL_SANDBOX_MEMORY_LIMIT_MIB,
});

const CPU_USD_PER_CORE_SECOND = 0.00003942;
const MEMORY_USD_PER_GIB_SECOND = 0.00000667;
const MEMORY_GIB = MODAL_SANDBOX_MEMORY_LIMIT_MIB / 1024;

export const MODAL_SANDBOX_COST_CEILING_USD = WORKLOADS.tiny_stories.cost_ceiling_usd;
export const MODAL_PRICING_SOURCE = "https://modal.com/pricing";
export const MODAL_PRICING_CHECKED_AT = "2026-11-14";

export function estimateModalSandboxCostUsd(runtimeSeconds) {
  const raw = runtimeSeconds * (
    CPU_USD_PER_CORE_SECOND * MODAL_SANDBOX_CPU_LIMIT_CORES +
    MEMORY_USD_PER_GIB_SECOND * MEMORY_GIB
  );
  // Estimate maximum CPU/memory usage within the hard resource limits; round
  // up to four decimals so the displayed amount does not understate the rate.
  return (Math.ceil(raw * 10000) / 10000).toFixed(4);
}
