import hashlib
from pathlib import Path

import pytest

from custom_training_dependencies import download_locked_wheels


def test_download_uses_the_manifest_python_abi_and_hash_pinned_wheels(tmp_path):
    wheel = b"wheel-bytes"
    wheel_hash = hashlib.sha256(wheel).hexdigest()
    lock = tmp_path / "requirements.lock"
    lock.write_text(f"demo-package==1.0 --hash=sha256:{wheel_hash}\n", encoding="utf-8")
    destination = tmp_path / "wheelhouse"
    observed = {}

    def run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        target = Path(command[command.index("--dest") + 1])
        (target / "demo_package-1.0-py3-none-any.whl").write_bytes(wheel)

    result = download_locked_wheels(lock, destination, python_version="3.11", run=run)
    command = observed["command"]
    assert command[command.index("--python-version") + 1] == "3.11"
    assert command[command.index("--implementation") + 1] == "cp"
    abis = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--abi"]
    assert abis == ["cp311", "abi3", "none"]
    assert "--only-binary=:all:" in command and "--require-hashes" in command
    assert observed["kwargs"]["timeout"] == 90
    assert result["packages"] == 1
    assert result["bytes"] == len(wheel)


def test_download_rejects_a_python_version_outside_the_manifest_contract(tmp_path):
    lock = tmp_path / "requirements.lock"
    lock.write_text("demo-package==1.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="training_python_version_invalid"):
        download_locked_wheels(lock, tmp_path / "wheelhouse", python_version="3.10",
                               run=lambda *_args, **_kwargs: pytest.fail("must not invoke pip"))
