/** Authoritative bounds for the reviewed MAP and owner-selected training lanes. */
export const MAP_TRAINING_MAX_COST_MICROUSD = 250_000;
export const MAP_TRAINING_MAX_RUNTIME_SECONDS = 120;
export const MAP_TRAINING_MAX_MONTHLY_MICROUSD = 1_000_000;
export const MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD = "1.00";
export const OWNER_TRAINING_MAX_MONTHLY_MICROUSD = 30_000_000;
export const OWNER_TRAINING_MAX_COST_MICROUSD = 1_000_000;

export const DEFAULT_MAP_EXECUTION = Object.freeze({
  dataset: "papers",
  run_name: "map44m",
  steps: 100000,
});
