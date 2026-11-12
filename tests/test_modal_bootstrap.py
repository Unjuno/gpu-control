from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODAL_DIR = Path(__file__).resolve().parents[1] / "sites" / "gpu-control-sites" / "modal"
sys.path.insert(0, str(MODAL_DIR))
import gpu_control_modal_bootstrap as modal_bootstrap  # noqa: E402
from gpu_control_modal_bootstrap import sandbox_entrypoint  # noqa: E402


class SandboxBootstrapTests(unittest.TestCase):
    def run_script(self, source: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "inference.py"
            script.write_text(source, encoding="utf-8")
            command = sandbox_entrypoint(str(script), drop_privileges=False)
            return subprocess.run(command, capture_output=True, text=True, check=False)

    def test_main_return_two_emits_line_and_system_exit_markers(self) -> None:
        source = "\n" * 74 + "def main():\n    return 2\n\n"
        source += "if __name__ == '__main__':\n    raise SystemExit(main())\n"
        result = self.run_script(source)
        self.assertEqual(result.returncode, 140)
        self.assertIn("GPU_CONTROL_PREFLIGHT_RETURN_LINE=76", result.stderr)
        self.assertNotIn("GPU_CONTROL_SANDBOX_SYSTEM_EXIT=2", result.stderr)
        self.assertEqual(modal_bootstrap.diagnostic_code_for_exit(result.returncode), "PREFLIGHT_RETURN_LINE_76")

    def test_system_exit_before_main_still_emits_fallback_marker(self) -> None:
        result = self.run_script("raise SystemExit(2)\n")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("GPU_CONTROL_PREFLIGHT_RETURN_LINE=", result.stderr)
        self.assertIn("GPU_CONTROL_SANDBOX_SYSTEM_EXIT=2", result.stderr)

    def test_preflight_exit_codes_are_limited_to_registered_guard_lines(self) -> None:
        expected = {43, 47, 56, 58, 62, 69, 72, 76}
        self.assertTrue(hasattr(modal_bootstrap, "preflight_exit_code_map"))
        self.assertTrue(hasattr(modal_bootstrap, "diagnostic_code_for_exit"))
        self.assertTrue(hasattr(modal_bootstrap, "normalize_exit_code"))
        mapping = modal_bootstrap.preflight_exit_code_map()
        self.assertEqual({code - 64 for code in mapping}, expected)
        self.assertIsNone(modal_bootstrap.diagnostic_code_for_exit(64 + 75))
        self.assertEqual(
            modal_bootstrap.normalize_exit_code(64 + 76),
            (2, "PREFLIGHT_RETURN_LINE_76"),
        )
        self.assertEqual(modal_bootstrap.normalize_exit_code(2), (2, None))
        workload = (MODAL_DIR.parent / "workloads" / "tiny_stories_inference" / "inference.py").read_text()
        lines = workload.splitlines()
        self.assertTrue(all(lines[line - 1].strip() == "return 2" for line in expected))

    def test_real_inference_missing_identity_emits_bounded_guard_diagnostic(self) -> None:
        inference = MODAL_DIR.parent / "workloads" / "tiny_stories_inference" / "inference.py"
        command = sandbox_entrypoint(str(inference), drop_privileges=False)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        self.assertEqual(result.returncode, 64 + 43)
        self.assertIn("GPU_CONTROL_PREFLIGHT_RETURN_LINE=43", result.stderr)
        self.assertEqual(
            modal_bootstrap.normalize_exit_code(result.returncode),
            (2, "PREFLIGHT_RETURN_LINE_43"),
        )

    def test_production_command_keeps_privilege_drop_and_isolated_python(self) -> None:
        command = sandbox_entrypoint()
        self.assertEqual(command[:3], ("python", "-I", "-c"))
        self.assertIn("os.setgroups([])", command[3])
        self.assertIn("os.setgid(10001)", command[3])
        self.assertIn("os.setuid(10001)", command[3])

    def test_modal_api_image_uses_hash_locked_framework_dependencies(self) -> None:
        requirements = (MODAL_DIR / "requirements.txt").read_text(encoding="utf-8")
        app_source = (MODAL_DIR / "app.py").read_text(encoding="utf-8")
        pins = {line.split("\\", 1)[0].strip() for line in requirements.splitlines()
                if line.startswith(("fastapi==", "starlette=="))}
        self.assertIn("fastapi==0.162.2", pins)
        self.assertIn("starlette==1.10.0", pins)
        self.assertIn(".pip_install_from_requirements(str(SITE_ROOT / \"modal\" / \"requirements.txt\"))", app_source)
        self.assertGreaterEqual(requirements.count("--hash=sha256:"), 11)


if __name__ == "__main__":
    unittest.main()
