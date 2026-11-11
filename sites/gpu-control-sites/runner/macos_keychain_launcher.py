#!/usr/bin/env python3
"""Start the fixed Sites Runner with credentials read from macOS Keychain."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SERVICE = "com.unjuno.gpu-control.runner"
SECURITY = "/usr/bin/security"
ACCOUNTS = {
    "GPU_CONTROL_RUNNER_BEARER_TOKEN": "runner-bearer",
    "GPU_CONTROL_SITES_SERVICE_TOKEN": "sites-service",
}


class KeychainUnavailable(Exception):
    pass


def read_secret(account: str) -> str:
    if account not in ACCOUNTS.values():
        raise KeychainUnavailable
    try:
        result = subprocess.run(
            [SECURITY, "find-generic-password", "-s", SERVICE, "-a", account, "-w"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise KeychainUnavailable from None
    if result.returncode != 0:
        raise KeychainUnavailable
    try:
        value = result.stdout.rstrip(b"\r\n").decode("utf-8")
    except UnicodeDecodeError:
        raise KeychainUnavailable from None
    if not value:
        raise KeychainUnavailable
    return value


def load_secrets() -> dict[str, str]:
    return {name: read_secret(account) for name, account in ACCOUNTS.items()}


def main() -> int:
    runner_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(runner_dir))
    import run  # noqa: PLC0415

    try:
        run.set_keychain_secrets(load_secrets())
    except (KeychainUnavailable, run.RunnerError):
        run.safe_log("KEYCHAIN_SECRET_UNAVAILABLE")
        return 2
    return run.main()


if __name__ == "__main__":
    raise SystemExit(main())
