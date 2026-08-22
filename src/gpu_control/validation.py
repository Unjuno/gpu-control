from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
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


def validate_repo(value: str) -> str:
    if not _REPO_RE.fullmatch(value):
        raise ValidationError("target_repo must use owner/repository syntax")
    return value


def validate_sha(value: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise ValidationError("target_sha must be an immutable 40-character hexadecimal commit SHA")
    return value.lower()


def validate_relative_path(value: str) -> str:
    if not value or "\\" in value:
        raise ValidationError("dockerfile_path must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValidationError("dockerfile_path must not be absolute or contain traversal segments")
    return str(path)


def validate_profile(value: str) -> str:
    if not _PROFILE_RE.fullmatch(value):
        raise ValidationError("gpu_profile contains unsupported characters")
    return value


def parse_runtime(value: str | int) -> int:
    try:
        runtime = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("max_runtime_minutes must be an integer") from exc
    if runtime <= 0:
        raise ValidationError("max_runtime_minutes must be greater than zero")
    return runtime


def parse_cost(value: str | Decimal) -> Decimal:
    try:
        cost = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("max_cost_usd must be a decimal number") from exc
    if not cost.is_finite() or cost <= 0:
        raise ValidationError("max_cost_usd must be a finite positive number")
    return cost.quantize(Decimal("0.01"))


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
