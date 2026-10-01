from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ValidationError(ValueError):
    """Raised when a workload request violates the public input contract."""


@dataclass(frozen=True)
class WorkloadRequest:
    target_repo: str
    target_sha: str
    dockerfile_path: str
    gpu_profile: str
    max_runtime_minutes: int
    max_cost_usd: Decimal


def _validate_text(value: object, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValidationError(f"{field} must be a non-empty bounded string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{field} must not contain control characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{field} must be valid UTF-8 text") from exc
    return value


def validate_repo(value: str) -> str:
    _validate_text(value, "target_repo", 512)
    if not _REPO_RE.fullmatch(value) or any(part in {".", ".."} for part in value.split("/")):
        raise ValidationError("target_repo must use owner/repository syntax")
    return value


def validate_sha(value: str) -> str:
    _validate_text(value, "target_sha", 40)
    if not _SHA_RE.fullmatch(value):
        raise ValidationError("target_sha must be an immutable 40-character hexadecimal commit SHA")
    return value.lower()


def validate_relative_path(value: str) -> str:
    _validate_text(value, "dockerfile_path", 1024)
    if "\\" in value:
        raise ValidationError("dockerfile_path must be a POSIX relative path")
    # Check the original spelling; PurePosixPath would erase '.' and empty parts.
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValidationError("dockerfile_path is not canonical: require a relative path without traversal segments")
    return value


def validate_profile(value: str) -> str:
    _validate_text(value, "gpu_profile", 64)
    if not _PROFILE_RE.fullmatch(value):
        raise ValidationError("gpu_profile contains unsupported characters")
    return value


def parse_runtime(value: str | int) -> int:
    if type(value) is int:
        runtime = value
    elif isinstance(value, str) and len(value) <= 10 and re.fullmatch(r"[0-9]+", value):
        runtime = int(value)
    else:
        raise ValidationError("max_runtime_minutes must be an integer or ASCII digit string")
    if runtime <= 0:
        raise ValidationError("max_runtime_minutes must be greater than zero")
    return runtime


def parse_cost(value: str | Decimal) -> Decimal:
    if not isinstance(value, (str, Decimal)) or len(str(value)) > 64:
        raise ValidationError("max_cost_usd must be a bounded decimal string or Decimal")
    try:
        cost = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("max_cost_usd must be a decimal number") from exc
    if not cost.is_finite() or cost <= 0:
        raise ValidationError("max_cost_usd must be a finite positive number")
    if cost.as_tuple().exponent < -2:
        raise ValidationError("max_cost_usd must use at most two decimal places")
    try:
        return cost.quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValidationError("max_cost_usd exceeds supported decimal precision") from exc


def build_request(
    *,
    target_repo: str,
    target_sha: str,
    dockerfile_path: str,
    gpu_profile: str,
    max_runtime_minutes: str | int,
    max_cost_usd: str | Decimal,
) -> WorkloadRequest:
    return WorkloadRequest(
        target_repo=validate_repo(target_repo),
        target_sha=validate_sha(target_sha),
        dockerfile_path=validate_relative_path(dockerfile_path),
        gpu_profile=validate_profile(gpu_profile),
        max_runtime_minutes=parse_runtime(max_runtime_minutes),
        max_cost_usd=parse_cost(max_cost_usd),
    )
