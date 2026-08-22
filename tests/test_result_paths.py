import pytest

from gpu_control.results import (
    ArtifactDisposition,
    OutputArtifact,
    ResultContractError,
    load_result_policy,
)


def make_artifact(name: str) -> OutputArtifact:
    return OutputArtifact(
        name=name,
        sha256="sha256:" + "a" * 64,
        size_bytes=1,
        media_type="application/octet-stream",
        reference="provider://job/artifact",
        disposition=ArtifactDisposition.COLLECTED,
    )


@pytest.mark.parametrize(
    "name",
    [
        "a//b.bin",
        "a/./b.bin",
        "a/../b.bin",
        "../b.bin",
        "/absolute.bin",
        "windows\\path.bin",
    ],
)
def test_ambiguous_or_traversing_artifact_paths_are_rejected(name: str) -> None:
    with pytest.raises(ResultContractError, match="artifact name"):
        make_artifact(name).validate_shape(load_result_policy())
