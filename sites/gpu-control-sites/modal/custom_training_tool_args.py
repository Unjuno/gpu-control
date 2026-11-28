"""Project validated MCP training inputs onto the private adapter lifecycle."""


def lifecycle_arguments(tool, arguments, *, plan=None):
    """Keep the adapter bridge's action-specific argument contract explicit."""
    fields = {
        "training_submit": ("run_id", "plan_fingerprint", "authorization_expires_at", "source_token"),
        "training_status": ("run_id", "plan_fingerprint", "approved_plan"),
        "training_cancel": ("run_id", "plan_fingerprint", "approved_plan"),
        "training_checkpoint": ("run_id", "plan_fingerprint", "approved_plan", "offset", "max_bytes"),
        "training_artifact": ("run_id", "plan_fingerprint", "approved_plan", "artifact_id", "offset", "max_bytes"),
    }
    if tool not in fields or not isinstance(arguments, dict):
        raise ValueError("invalid_training_action")
    projected = {key: arguments[key] for key in fields[tool] if key in arguments}
    if tool == "training_submit":
        if not isinstance(plan, dict):
            raise ValueError("custom_training_plan_missing")
        projected.update(plan=plan, approved_plan=plan)
    elif not isinstance(projected.get("approved_plan"), dict):
        raise ValueError("custom_training_plan_missing")
    return projected
