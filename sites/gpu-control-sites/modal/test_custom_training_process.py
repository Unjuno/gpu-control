import sys
import time
import os

import pytest

from custom_training_process import run_command


def test_command_runs_as_argv_without_inheriting_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_SECRET", "sensitive")
    result = run_command([sys.executable, "-c", "import os; print(os.getenv('PROVIDER_SECRET', 'absent'))"],
                         tmp_path, 5)
    assert result["state"] == "succeeded"
    assert result["output"].strip() == "absent"


def test_timeout_and_output_truncation(tmp_path):
    result = run_command([sys.executable, "-c", "import time; print('x'*100, flush=True); time.sleep(10)"],
                         tmp_path, 1, output_limit=10)
    assert result["state"] == "timeout"
    assert result["output"] == "x" * 10
    assert result["output_truncated"] is True


def test_multibyte_output_stays_within_encoded_byte_limit(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import sys; sys.stdout.write('€' * 3000)"],
        tmp_path, 5, output_limit=8192)

    assert result["state"] == "succeeded"
    assert result["output_truncated"] is True
    assert len(result["output"].encode("utf-8")) <= 8192


def test_cancel_and_failure_are_distinct(tmp_path):
    start = time.monotonic()
    cancelled = run_command([sys.executable, "-c", "import time; time.sleep(10)"], tmp_path, 5,
                            cancelled=lambda: time.monotonic() - start > 0.1)
    failed = run_command([sys.executable, "-c", "raise SystemExit(7)"], tmp_path, 5)
    assert cancelled["state"] == "cancelled"
    assert failed["state"] == "failed" and failed["exit_code"] == 7


def test_invalid_command_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_command(["bad\x00arg"], tmp_path, 1)


def test_workload_privilege_drop_fails_closed_without_root(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 501)
    with pytest.raises(ValueError, match="cannot_drop_workload_privileges"):
        run_command([sys.executable, "-c", "pass"], tmp_path, 1, drop_privileges=True)


def test_gpu_evidence_requires_positive_trusted_sample(tmp_path):
    result = run_command([sys.executable, "-c", "import time; time.sleep(.3)"],
                         tmp_path, 2, on_poll=lambda: True)
    assert result["state"] == "succeeded"
    assert result["gpu_activity_seen"] is True
