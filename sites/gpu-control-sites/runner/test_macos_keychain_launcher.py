"""Tests for Keychain-backed, secret-free macOS Runner startup."""
from __future__ import annotations

import importlib.util
import contextlib
import io
import os
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
        secret = "opaque-test-secret-0123456789abcdef"
        with patch.object(keychain, "_read_keychain_item", return_value=secret) as read:
            self.assertEqual(keychain.read_secret("runner-bearer"), secret)
        read.assert_called_once_with(keychain.SERVICE, "runner-bearer")

    def test_unknown_account_and_keychain_failure_fail_closed(self):
        with self.assertRaises(keychain.KeychainUnavailable):
            keychain.read_secret("provider-token")
        with patch.object(keychain, "_read_keychain_item", side_effect=keychain.KeychainUnavailable):
            with self.assertRaises(keychain.KeychainUnavailable):
                keychain.read_secret("runner-bearer")

    def test_keychain_secret_set_is_complete_and_fixed(self):
        with patch.object(keychain, "read_secret", side_effect=lambda account: f"opaque-{account}"):
            values = keychain.load_secrets()
        self.assertEqual(set(values), set(keychain.ACCOUNTS))
        self.assertEqual(values["GPU_CONTROL_RUNNER_BEARER_TOKEN"], "opaque-runner-bearer")

    def test_runner_launcher_discards_unapproved_inherited_environment(self):
        allowed = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/Users/test",
            "LANG": "C",
            "GPU_CONTROL_SITE_URL": launch_agent.DEFAULT_SITE,
            "CPU_WORKLOAD_REPOSITORY": "Unjuno/gpu-control",
            "CPU_WORKLOAD_SOURCE_SHA": "a" * 40,
            "CPU_WORKLOAD_IMAGE_DIGEST": "sha256:" + "b" * 64,
            "GPU_CONTROL_RUNNER_POLL_SECONDS": "5",
        }
        inherited = {
            **allowed,
            "SSH_AUTH_SOCK": "/tmp/agent.sock",
            "SSH_AGENT_PID": "123",
            "HTTPS_PROXY": "http://attacker.invalid:8080",
            "DOCKER_HOST": "tcp://attacker.invalid:2375",
            "PYTHONPATH": "/tmp/untrusted",
            "GPU_CONTROL_RUNNER_BEARER_TOKEN": "must-not-use-env-secret",
        }
        with patch.dict("os.environ", inherited, clear=True):
            keychain.sanitize_process_environment()
            self.assertEqual(dict(os.environ), allowed)

    def test_launch_agent_pins_home_and_locale(self):
        document = launch_agent.build_plist(Path("/work/gpu-control"), "/usr/bin/python3", Path("/Users/test"))
        self.assertEqual(document["EnvironmentVariables"]["HOME"], "/Users/test")
        self.assertEqual(document["EnvironmentVariables"]["LANG"], "C")

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
        self.assertEqual(document["ProgramArguments"], [
            "/opt/homebrew/bin/python3", "-I", "-S",
            "/work/gpu-control/runner/macos_keychain_launcher.py",
        ])
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

    def test_install_copies_only_required_runner_files_to_private_runtime_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            runtime = root / "Application Support/Unjuno/gpu-control"
            home = root / "home"
            (source / "runner").mkdir(parents=True)
            (source / "runner/run.py").write_text("runner code", encoding="utf-8")
            (source / "runner/macos_keychain_launcher.py").write_text("launcher code", encoding="utf-8")
            (source / "runner/other.py").write_text("not copied", encoding="utf-8")
            with patch.object(sys, "argv", [
                "macos_launch_agent.py", "--install", "--repository-root", str(source),
                "--runtime-root", str(runtime), "--home", str(home), "--python", "/usr/bin/python3",
            ]), patch.object(launch_agent, "launchctl", return_value=subprocess.CompletedProcess([], 1, b"", b"")):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(launch_agent.main(), 0)
            installed = runtime / "runner"
            self.assertEqual((installed / "run.py").read_text(encoding="utf-8"), "runner code")
            self.assertEqual((installed / "macos_keychain_launcher.py").read_text(encoding="utf-8"), "launcher code")
            self.assertFalse((installed / "other.py").exists())
            self.assertEqual(installed.stat().st_mode & 0o777, 0o700)
            self.assertEqual((installed / "run.py").stat().st_mode & 0o777, 0o600)
            plist = plistlib.loads(launch_agent.plist_path(home).read_bytes())
            self.assertEqual(plist["ProgramArguments"][3], str((installed / "macos_keychain_launcher.py").resolve()))
            self.assertEqual(plist["WorkingDirectory"], str(runtime.resolve()))

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
