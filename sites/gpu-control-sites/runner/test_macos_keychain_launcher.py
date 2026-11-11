"""Tests for Keychain-backed, secret-free macOS Runner startup."""
from __future__ import annotations

import importlib.util
import contextlib
import io
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


keychain = load_module("macos_keychain_launcher_under_test", "macos_keychain_launcher.py")
launch_agent = load_module("macos_launch_agent_under_test", "macos_launch_agent.py")


class KeychainLauncherTests(unittest.TestCase):
    def test_secret_read_uses_fixed_keychain_identity_and_never_logs_value(self):
        secret = b"opaque-test-secret-0123456789abcdef"
        with patch.object(keychain.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, secret + b"\n", b"")) as run:
            self.assertEqual(keychain.read_secret("runner-bearer"), secret.decode())
        args = run.call_args.args[0]
        self.assertEqual(args, [keychain.SECURITY, "find-generic-password", "-s", keychain.SERVICE, "-a", "runner-bearer", "-w"])
        self.assertNotIn(secret.decode(), " ".join(args))

    def test_unknown_account_and_keychain_failure_fail_closed(self):
        with self.assertRaises(keychain.KeychainUnavailable):
            keychain.read_secret("provider-token")
        with patch.object(keychain.subprocess, "run", return_value=subprocess.CompletedProcess([], 44, b"", b"not found")):
            with self.assertRaises(keychain.KeychainUnavailable):
                keychain.read_secret("runner-bearer")

    def test_keychain_secret_set_is_complete_and_fixed(self):
        with patch.object(keychain, "read_secret", side_effect=lambda account: f"opaque-{account}"):
            values = keychain.load_secrets()
        self.assertEqual(set(values), set(keychain.ACCOUNTS))
        self.assertEqual(values["GPU_CONTROL_RUNNER_BEARER_TOKEN"], "opaque-runner-bearer")

    def test_runner_uses_keychain_values_instead_of_environment_secrets(self):
        runner = load_module("runner_config_under_test", "run.py")
        with patch.dict("os.environ", {
            "GPU_CONTROL_SITE_URL": "https://example.invalid",
            "GPU_CONTROL_RUNNER_BEARER_TOKEN": "environment-runner-secret-0123456789abcdef",
            "GPU_CONTROL_SITES_SERVICE_TOKEN": "environment-sites-secret-0123456789abcdef",
            "CPU_WORKLOAD_REPOSITORY": "Unjuno/gpu-control",
            "CPU_WORKLOAD_SOURCE_SHA": "3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288",
            "CPU_WORKLOAD_IMAGE_DIGEST": "sha256:" + "a" * 64,
        }, clear=True), patch.object(runner.shutil, "which", return_value="/usr/bin/docker"):
            runner.set_keychain_secrets({
                "GPU_CONTROL_RUNNER_BEARER_TOKEN": "keychain-runner-secret-0123456789abcdef",
                "GPU_CONTROL_SITES_SERVICE_TOKEN": "keychain-sites-secret-0123456789abcdef",
            })
            config = runner.config()
        self.assertEqual(config["runner_token"], "keychain-runner-secret-0123456789abcdef")
        self.assertEqual(config["sites_token"], "keychain-sites-secret-0123456789abcdef")

    def test_launch_agent_contains_only_nonsecret_configuration(self):
        document = launch_agent.build_plist(Path("/work/gpu-control"), "/opt/homebrew/bin/python3", Path("/Users/test"))
        encoded = plistlib.dumps(document).decode()
        self.assertEqual(document["Label"], launch_agent.LABEL)
        self.assertEqual(document["ProgramArguments"][1], "/work/gpu-control/runner/macos_keychain_launcher.py")
        self.assertEqual(document["EnvironmentVariables"]["GPU_CONTROL_SITE_URL"], launch_agent.DEFAULT_SITE)
        self.assertNotIn("RUNNER_BEARER_TOKEN", encoded)
        self.assertNotIn("SITES_SERVICE_TOKEN", encoded)
        self.assertNotIn("Bearer ", encoded)
        self.assertEqual(document["KeepAlive"], True)
        self.assertEqual(document["ThrottleInterval"], 30)

    def test_launch_agent_file_is_written_atomically_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Library/LaunchAgents" / f"{launch_agent.LABEL}.plist"
            document = launch_agent.build_plist(Path("/work/gpu-control"), "/usr/bin/python3", Path(tmp))
            launch_agent.write_plist(path, document)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(plistlib.loads(path.read_bytes()), document)

    def test_runner_process_inventory_only_returns_runner_commands(self):
        output = (" 123 /opt/python -c runpy.run_path('sites/gpu-control-sites/runner/run.py')\n"
                  " 456 /opt/python -m unittest test_macos_keychain_launcher\n"
                  " 789 /opt/python /Users/test/gpu-control/runner/macos_keychain_launcher.py\n").encode()
        with patch.object(launch_agent.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, b"")):
            processes = launch_agent.runner_processes()
        self.assertEqual(len(processes), 2)

    def test_start_does_not_force_restart_a_loaded_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = launch_agent.plist_path(home)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"installed")
            with patch.object(sys, "argv", ["macos_launch_agent.py", "--start", "--home", tmp]), \
                 patch.object(launch_agent, "launchctl", return_value=subprocess.CompletedProcess([], 0, b"", b"")) as ctl, \
                 patch.object(launch_agent, "runner_processes") as processes, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(launch_agent.main(), 0)
            self.assertEqual(ctl.call_args_list[0].args, ("print", f"{launch_agent.domain()}/{launch_agent.LABEL}"))
            self.assertEqual(ctl.call_count, 1)
            processes.assert_not_called()
            self.assertIn("already loaded", output.getvalue())

    def test_start_refuses_to_create_a_second_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = launch_agent.plist_path(home)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"installed")
            with patch.object(sys, "argv", ["macos_launch_agent.py", "--start", "--home", tmp]), \
                 patch.object(launch_agent, "launchctl", return_value=subprocess.CompletedProcess([], 1, b"", b"not loaded")) as ctl, \
                 patch.object(launch_agent, "runner_processes", return_value=["123 python runner/run.py"]):
                with self.assertRaises(SystemExit) as raised:
                    launch_agent.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(ctl.call_count, 1)


if __name__ == "__main__":
    unittest.main()
