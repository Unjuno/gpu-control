from __future__ import annotations

from dataclasses import dataclass
import re


_IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ContainerVerificationResult:
    """Evidence produced by an isolated container-verification stage.

    This object carries workload identity and the security properties required by
    the paid-compute gate. It is intentionally more specific than a boolean so a
    provider path cannot treat an unrelated or partially verified container as
    approved evidence.
    """

    repository: str
    commit_sha: str
    dockerfile_path: str
    image_digest: str
    verification_reference: str
    build_isolated: bool
    runtime_isolated: bool
    smoke_test_passed: bool
    output_contract_verified: bool
    credentials_absent: bool
    network_policy_enforced: bool
    resource_limits_enforced: bool

    def validate_shape(self) -> None:
        if not _IMAGE_DIGEST_RE.fullmatch(self.image_digest):
            raise ValueError("image_digest must be a lowercase sha256 digest")
        if not self.verification_reference.strip():
            raise ValueError("verification_reference is required")
