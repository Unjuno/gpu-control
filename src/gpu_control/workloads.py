from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re

from .validation import ValidationError, validate_repo, validate_sha


class AcceleratorKind(str, Enum):
    CPU = "cpu"
    GPU = "gpu"


class NetworkRequirement(str, Enum):
    DISABLED = "disabled"
    RESTRICTED = "restricted"
    REQUIRED = "required"


class ResultTransport(str, Enum):
    SHARED_FILESYSTEM = "shared_filesystem"
    OBJECT_STORAGE = "object_storage"
    DATABASE = "database"
    STDOUT = "stdout"


_WORKLOAD_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def _json_value(value):  # type: ignore[no-untyped-def]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class WorkloadRequirements:
    """Immutable, operator-owned compute and result requirements."""

    workload_id: str
    source_repository: str
    source_sha: str
    operating_system: str
    architecture: str
    accelerator_kind: AcceleratorKind
    gpu_profile: str | None
    gpu_count: int
    minimum_vram_mib: int
    minimum_cpu_cores: Decimal
    minimum_memory_mib: int
    max_runtime_seconds: int
    network_requirement: NetworkRequirement
    result_transport: ResultTransport
    max_result_bytes: int
    cancellation_required: bool
    cleanup_proof_required: bool

    def __post_init__(self) -> None:
        if not isinstance(self.workload_id, str) or not _WORKLOAD_ID.fullmatch(self.workload_id):
            raise ValueError("workload_id must be a canonical lowercase identifier")
        if not isinstance(self.source_repository, str) or not isinstance(self.source_sha, str):
            raise ValueError("source repository and revision are required text")
        try:
            validate_repo(self.source_repository)
            if validate_sha(self.source_sha) != self.source_sha:
                raise ValueError("source_sha must be lowercase canonical hexadecimal")
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        for field, value in (("operating_system", self.operating_system),
                             ("architecture", self.architecture)):
            if (not isinstance(value, str) or not value or value != value.strip() or
                    any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise ValueError(f"{field} must be nonempty canonical text")
        if not isinstance(self.accelerator_kind, AcceleratorKind):
            raise ValueError("accelerator_kind is unsupported")
        if not isinstance(self.network_requirement, NetworkRequirement):
            raise ValueError("network_requirement is unsupported")
        if not isinstance(self.result_transport, ResultTransport):
            raise ValueError("result_transport is unsupported")
        for field, value in (("gpu_count", self.gpu_count),
                             ("minimum_vram_mib", self.minimum_vram_mib),
                             ("minimum_memory_mib", self.minimum_memory_mib),
                             ("max_runtime_seconds", self.max_runtime_seconds),
                             ("max_result_bytes", self.max_result_bytes)):
            if type(value) is not int or value < 0:
                raise ValueError(f"{field} must be a nonnegative integer")
        if self.minimum_memory_mib == 0 or self.max_runtime_seconds == 0 or self.max_result_bytes == 0:
            raise ValueError("memory, runtime, and result-size limits must be positive")
        if (not isinstance(self.minimum_cpu_cores, Decimal) or
                not self.minimum_cpu_cores.is_finite() or self.minimum_cpu_cores <= 0):
            raise ValueError("minimum_cpu_cores must be a finite positive Decimal")
        if type(self.cancellation_required) is not bool or type(self.cleanup_proof_required) is not bool:
            raise ValueError("cancellation and cleanup requirements must be boolean")
        if self.accelerator_kind is AcceleratorKind.CPU:
            if self.gpu_profile is not None or self.gpu_count != 0 or self.minimum_vram_mib != 0:
                raise ValueError("CPU requirements must not require GPU")
        else:
            if (not isinstance(self.gpu_profile, str) or
                    not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", self.gpu_profile) or
                    self.gpu_count < 1 or self.minimum_vram_mib < 1):
                raise ValueError("GPU requirements need a profile, positive count, and minimum VRAM")

    def to_dict(self) -> dict[str, object]:
        return _json_value(asdict(self))

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return "sha256:" + digest
