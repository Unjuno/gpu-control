"""Provider-only contracts with no Gateway, database, OAuth, or host imports."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactPayload:
    artifact_id: str
    data: bytes
    media_type: str


@dataclass(frozen=True)
class Observation:
    state: str
    result: dict | None = None
    artifacts: tuple[ArtifactPayload, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in {"running", "succeeded", "failed", "cancelled"}:
            raise ValueError("Provider returned an unsupported state")


def bounded_text(chunks, maximum: int) -> tuple[str, bool]:
    if type(maximum) is not int or maximum < 0:
        raise ValueError("maximum must be a nonnegative integer")
    output = bytearray()
    for chunk in chunks:
        raw = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
        remaining = maximum - len(output)
        output.extend(raw[:remaining])
        if len(raw) > remaining:
            return output.decode("utf-8", errors="replace"), True
    return output.decode("utf-8", errors="replace"), False
