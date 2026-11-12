#!/usr/bin/env python3
"""Start the fixed Sites Runner with credentials read from macOS Keychain."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

SERVICE = "com.unjuno.gpu-control.runner"
SECURITY_FRAMEWORK = "/System/Library/Frameworks/Security.framework/Security"
ACCOUNTS = {
    "GPU_CONTROL_RUNNER_BEARER_TOKEN": "runner-bearer",
    "GPU_CONTROL_SITES_SERVICE_TOKEN": "sites-service",
}
ENVIRONMENT_ALLOWLIST = (
    "HOME",
    "LANG",
    "PATH",
    "GPU_CONTROL_SITE_URL",
    "CPU_WORKLOAD_REPOSITORY",
    "CPU_WORKLOAD_SOURCE_SHA",
    "CPU_WORKLOAD_IMAGE_DIGEST",
    "GPU_CONTROL_RUNNER_POLL_SECONDS",
)


class KeychainUnavailable(Exception):
    pass


def _read_keychain_item(service: str, account: str) -> str:
    try:
        security = ctypes.CDLL(SECURITY_FRAMEWORK)
        set_interaction = security.SecKeychainSetUserInteractionAllowed
        set_interaction.argtypes = [ctypes.c_bool]
        set_interaction.restype = ctypes.c_int32
        if set_interaction(False) != 0:
            raise KeychainUnavailable

        find_password = security.SecKeychainFindGenericPassword
        find_password.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        find_password.restype = ctypes.c_int32
        free_content = security.SecKeychainItemFreeContent
        free_content.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        free_content.restype = ctypes.c_int32

        service_bytes = service.encode("utf-8")
        account_bytes = account.encode("utf-8")
        password_length = ctypes.c_uint32()
        password_data = ctypes.c_void_p()
        item = ctypes.c_void_p()
        status = find_password(
            None,
            len(service_bytes),
            service_bytes,
            len(account_bytes),
            account_bytes,
            ctypes.byref(password_length),
            ctypes.byref(password_data),
            ctypes.byref(item),
        )
        if status != 0 or not password_data.value or password_length.value == 0:
            raise KeychainUnavailable
        try:
            value = ctypes.string_at(password_data.value, password_length.value).decode("utf-8")
        finally:
            free_content(None, password_data)
    except (OSError, AttributeError, UnicodeDecodeError, KeychainUnavailable):
        raise KeychainUnavailable from None
    if not value:
        raise KeychainUnavailable
    return value


def read_secret(account: str) -> str:
    if account not in ACCOUNTS.values():
        raise KeychainUnavailable
    return _read_keychain_item(SERVICE, account)


def load_secrets() -> dict[str, str]:
    return {name: read_secret(account) for name, account in ACCOUNTS.items()}


def sanitize_process_environment() -> None:
    """Drop launchd/user environment that the fixed Runner does not need."""
    allowed = {name: os.environ[name] for name in ENVIRONMENT_ALLOWLIST if name in os.environ}
    os.environ.clear()
    os.environ.update(allowed)


def main() -> int:
    sanitize_process_environment()
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
