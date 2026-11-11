"""Recovery tests for expired Runner leases and orphaned containers."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

runner_dir = Path(__file__).resolve().parents[2] / "sites" / "gpu-control-sites" / "runner"
sys.path.insert(0, str(runner_dir))
import run as runner  # noqa: E402


class RunnerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"image_digest": "sha256:" + "a" * 64}
        self.row = {
            "run_id": "b" * 32,
            "lease_id": "c" * 32,
            "plan_fingerprint": "d" * 64,
            "source_sha": "e" * 40,
            "image_digest": self.cfg["image_digest"],
        }
        self.container_id = "f" * 64
        self.labels = {
            "io.unjuno.gpu-control.run-id": self.row["run_id"],
            "io.unjuno.gpu-control.plan-sha256": self.row["plan_fingerprint"],
            "io.unjuno.gpu-control.image-digest": self.row["image_digest"],
            "io.unjuno.gpu-control.source-sha": self.row["source_sha"],
        }

    def test_recovery_removes_only_matching_container_then_acknowledges_absence(self):
        inspect = json.dumps({"Config": {"Labels": self.labels}}).encode()
        with patch.object(runner, "post", side_effect=[{"recoveries": [self.row]}, {"ok": True}]) as post, \
             patch.object(runner, "container_ids", side_effect=[[self.container_id], []]), \
             patch.object(runner, "docker", side_effect=[inspect, b""]) as docker:
            runner.recover(self.cfg)

        docker.assert_has_calls([
            call(["inspect", "--format", "{{json .}}", self.container_id], 10),
            call(["rm", "--force", self.container_id], 15),
        ])
        receipt = {"absent": True, **self.row}
        post.assert_has_calls([call(self.cfg, "/runner/recoveries"), call(self.cfg, "/runner/recover", receipt)])

    def test_recovery_refuses_container_with_mismatched_identity_labels(self):
        bad_labels = {**self.labels, "io.unjuno.gpu-control.plan-sha256": "0" * 64}
        inspect = json.dumps({"Config": {"Labels": bad_labels}}).encode()
        with patch.object(runner, "post", return_value={"recoveries": [self.row]}) as post, \
             patch.object(runner, "container_ids", return_value=[self.container_id]), \
             patch.object(runner, "docker", return_value=inspect) as docker:
            with self.assertRaisesRegex(runner.RunnerError, "RECOVERY_LABEL_MISMATCH"):
                runner.recover(self.cfg)

        self.assertEqual(docker.call_count, 1)
        post.assert_called_once_with(self.cfg, "/runner/recoveries")

    def test_recovery_fails_closed_when_container_remains_after_removal(self):
        inspect = json.dumps({"Config": {"Labels": self.labels}}).encode()
        with patch.object(runner, "post", return_value={"recoveries": [self.row]}) as post, \
             patch.object(runner, "container_ids", side_effect=[[self.container_id], [self.container_id]]), \
             patch.object(runner, "docker", side_effect=[inspect, b""]):
            with self.assertRaisesRegex(runner.RunnerError, "RECOVERY_CLEANUP_UNCONFIRMED"):
                runner.recover(self.cfg)

        post.assert_called_once_with(self.cfg, "/runner/recoveries")


if __name__ == "__main__":
    unittest.main()
