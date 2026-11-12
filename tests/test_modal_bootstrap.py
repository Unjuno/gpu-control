from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODAL_DIR = Path(__file__).resolve().parents[1] / "sites" / "gpu-control-sites" / "modal"
sys.path.insert(0, str(MODAL_DIR))
from gpu_control_modal_bootstrap import sandbox_entrypoint  # noqa: E402


class SandboxBootstrapTests(unittest.TestCase):
    def run_script(self, source: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "inference.py"
            script.write_text(source, encoding="utf-8")
            command = sandbox_entrypoint(str(script), drop_privileges=False)
            return subprocess.run(command, capture_output=True, text=True, check=False)

    def test_main_return_two_emits_line_and_system_exit_markers(self) -> None:
        result = self.run_script(
            "def main():\n    return 2\n\n"
            "if __name__ == '__main__':\n    raise SystemExit(main())\n"
        )
        self.assertEqual(result.returncode, 2)
        self.assertRegex(result.stderr, r"GPU_CONTROL_PREFLIGHT_RETURN_LINE=[1-9][0-9]*")
        self.assertIn("GPU_CONTROL_SANDBOX_SYSTEM_EXIT=2", result.stderr)

    def test_system_exit_before_main_still_emits_fallback_marker(self) -> None:
        result = self.run_script("raise SystemExit(2)\n")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("GPU_CONTROL_PREFLIGHT_RETURN_LINE=", result.stderr)
        self.assertIn("GPU_CONTROL_SANDBOX_SYSTEM_EXIT=2", result.stderr)

    def test_production_command_keeps_privilege_drop_and_isolated_python(self) -> None:
        command = sandbox_entrypoint()
        self.assertEqual(command[:3], ("python", "-I", "-c"))
        self.assertIn("os.setgroups([])", command[3])
        self.assertIn("os.setgid(10001)", command[3])
        self.assertIn("os.setuid(10001)", command[3])


if __name__ == "__main__":
    unittest.main()
