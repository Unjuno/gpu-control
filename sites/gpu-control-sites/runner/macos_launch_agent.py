#!/usr/bin/env python3
"""Render a secret-free macOS LaunchAgent for the fixed Sites Runner."""
from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

LABEL = "com.unjuno.gpu-control.runner"
LAUNCHCTL = "/bin/launchctl"
DEFAULT_SITE = "https://gpu-control-sites.unjuno.chatgpt.site"
DEFAULT_REPOSITORY = "Unjuno/gpu-control"
DEFAULT_SOURCE_SHA = "3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288"
DEFAULT_IMAGE_DIGEST = "sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541"
PATH = "/run/current-system/sw/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def build_plist(repository_root: Path, python_executable: str, home: Path) -> dict:
    launcher = repository_root / "runner/macos_keychain_launcher.py"
    logs = home / "Library/Logs"
    return {
        "Label": LABEL,
        "ProgramArguments": [python_executable, str(launcher)],
        "WorkingDirectory": str(repository_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": str(logs / "gpu-control-runner.log"),
        "StandardErrorPath": str(logs / "gpu-control-runner.log"),
        "EnvironmentVariables": {
            "PATH": PATH,
            "GPU_CONTROL_SITE_URL": DEFAULT_SITE,
            "CPU_WORKLOAD_REPOSITORY": DEFAULT_REPOSITORY,
            "CPU_WORKLOAD_SOURCE_SHA": DEFAULT_SOURCE_SHA,
            "CPU_WORKLOAD_IMAGE_DIGEST": DEFAULT_IMAGE_DIGEST,
            "GPU_CONTROL_RUNNER_POLL_SECONDS": "5",
        },
    }


def plist_path(home: Path) -> Path:
    return home / "Library/LaunchAgents" / f"{LABEL}.plist"


def domain() -> str:
    return f"gui/{os.getuid()}"


def launchctl(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([LAUNCHCTL, *arguments], capture_output=True, check=False, timeout=30)


def runner_processes() -> list[str]:
    result = subprocess.run(["/bin/ps", "-axo", "pid=,command="], capture_output=True, check=False, timeout=10)
    if result.returncode != 0:
        raise RuntimeError("PROCESS_INVENTORY_UNAVAILABLE")
    lines = result.stdout.decode("utf-8", "replace").splitlines()
    return [line.strip() for line in lines if "runner/run.py" in line or
            "runner/macos_keychain_launcher.py" in line]


def write_plist(path: Path, document: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = plistlib.dumps(document, fmt=plistlib.FMT_XML)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{LABEL}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--render", action="store_true", help="write the LaunchAgent plist to stdout")
    actions.add_argument("--install", action="store_true", help="write the secret-free plist with mode 0600")
    actions.add_argument("--start", action="store_true", help="load or restart the installed LaunchAgent")
    actions.add_argument("--stop", action="store_true", help="stop and unload the LaunchAgent")
    actions.add_argument("--status", action="store_true", help="report whether the LaunchAgent is loaded")
    actions.add_argument("--uninstall", action="store_true", help="stop and remove only the LaunchAgent plist")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    document = plistlib.dumps(build_plist(args.repository_root.resolve(), args.python, args.home), fmt=plistlib.FMT_XML)
    target = plist_path(args.home)
    service = f"{domain()}/{LABEL}"
    loaded = launchctl("print", service).returncode == 0
    if args.render:
        sys.stdout.buffer.write(document)
    elif args.install:
        if loaded:
            parser.error("LaunchAgent is loaded; stop it before replacing the plist")
        write_plist(target, plistlib.loads(document))
        print(f"installed {target}")
    elif args.start:
        if not target.is_file():
            parser.error("LaunchAgent plist is not installed")
        if loaded:
            print("already loaded")
            return 0
        if runner_processes():
            parser.error("an unmanaged Runner is already running; stop it before starting LaunchAgent")
        result = launchctl("enable", service)
        if result.returncode != 0:
            sys.stderr.write(result.stderr.decode("utf-8", "replace"))
            return result.returncode or 1
        result = launchctl("bootstrap", domain(), str(target))
        if result.returncode != 0:
            sys.stderr.write(result.stderr.decode("utf-8", "replace"))
            return result.returncode or 1
        print("started")
    elif args.stop or args.uninstall:
        if loaded:
            result = launchctl("bootout", service)
            if result.returncode != 0:
                sys.stderr.write(result.stderr.decode("utf-8", "replace"))
                return result.returncode or 1
            if runner_processes():
                sys.stderr.write("Runner process remains after launchd bootout\n")
                return 1
        elif runner_processes():
            sys.stderr.write("unmanaged Runner is active; stop it through its current supervisor\n")
            return 1
        if args.uninstall and target.exists():
            target.unlink()
        print("stopped" if args.stop else "uninstalled")
    elif args.status:
        print("loaded" if loaded else "not loaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
