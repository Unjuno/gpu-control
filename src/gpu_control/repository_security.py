from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class RepositorySecurityError(ValueError):
    """Raised when repository controls are insufficient for paid execution."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepositorySecurityError(f"{field} is required")
    if value != value.strip():
        raise RepositorySecurityError(f"{field} must not contain surrounding whitespace")
    return value


@dataclass(frozen=True)
class RepositorySecurityEvidence:
    """Trusted evidence for GitHub repository controls guarding paid workflow code.

    This is intentionally separate from the repository policy file. A policy saying
    that main *should* be protected is not proof that GitHub is actually enforcing
    protection. A trusted preflight must read GitHub's repository/branch settings and
    construct this evidence before live paid authorization can succeed.
    """

    repository: str
    branch: str
    branch_protected: bool
    pull_request_required: bool
    required_status_checks_enforced: bool
    required_status_checks: tuple[str, ...]
    force_pushes_blocked: bool
    deletions_blocked: bool
    verification_reference: str
    schema_version: int = 1

    def validate_against_policy(self, policy: Mapping[str, Any]) -> None:
        if self.schema_version != 1:
            raise RepositorySecurityError("unsupported repository security evidence schema_version")

        identity = policy.get("github_identity")
        controls = policy.get("github_repository_security")
        if not isinstance(identity, Mapping):
            raise RepositorySecurityError("github_identity policy is required")
        if not isinstance(controls, Mapping):
            raise RepositorySecurityError("github_repository_security policy is required")

        expected_repository = _text(identity.get("repository"), "policy repository")
        expected_ref = _text(identity.get("ref"), "policy ref")
        if not expected_ref.startswith("refs/heads/"):
            raise RepositorySecurityError("paid policy ref must identify a branch")
        expected_branch = expected_ref.removeprefix("refs/heads/")

        if _text(self.repository, "repository") != expected_repository:
            raise RepositorySecurityError("repository security evidence repository mismatch")
        if _text(self.branch, "branch") != expected_branch:
            raise RepositorySecurityError("repository security evidence branch mismatch")
        if not _text(self.verification_reference, "verification_reference"):
            raise RepositorySecurityError("repository security verification reference is required")

        required_booleans = {
            "branch protection": (self.branch_protected, controls.get("branch_protection_required")),
            "pull request requirement": (self.pull_request_required, controls.get("pull_request_required")),
            "required status checks": (
                self.required_status_checks_enforced,
                controls.get("required_status_checks_required"),
            ),
            "force-push blocking": (self.force_pushes_blocked, controls.get("force_pushes_forbidden")),
            "branch deletion blocking": (self.deletions_blocked, controls.get("deletions_forbidden")),
        }
        for label, (actual, required) in required_booleans.items():
            if required is not True:
                raise RepositorySecurityError(f"paid policy must require {label}")
            if actual is not True:
                raise RepositorySecurityError(f"GitHub repository does not enforce required {label}")

        expected_checks = controls.get("required_status_checks")
        if not isinstance(expected_checks, list) or not expected_checks or not all(
            isinstance(item, str) and item.strip() for item in expected_checks
        ):
            raise RepositorySecurityError("paid policy must list required status checks")
        if len(set(expected_checks)) != len(expected_checks):
            raise RepositorySecurityError("paid policy required status checks must be unique")

        actual_checks = tuple(_text(item, "required status check") for item in self.required_status_checks)
        if len(set(actual_checks)) != len(actual_checks):
            raise RepositorySecurityError("repository security status checks must be unique")
        missing = sorted(set(expected_checks) - set(actual_checks))
        if missing:
            raise RepositorySecurityError(
                "GitHub branch protection is missing required status checks: " + ", ".join(missing)
            )
