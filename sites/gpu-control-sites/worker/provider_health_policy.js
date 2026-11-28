/** Shared ceilings for provider health diagnostics. These calls can incur
 * provider control-plane charges, so cooldown policy has one explicit owner. */
export const MODAL_HEALTH_CHECK_COOLDOWN_SECONDS = 60;
