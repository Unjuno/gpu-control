"""Regression tests for Site Runner endpoint and credential handling."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as runner  # noqa: E402


class RunnerHttpSecurityTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "GPU_CONTROL_SITE_URL": "https://gpu-control.example/",
            "GPU_CONTROL_RUNNER_BEARER_TOKEN": "r" * 48,
            "GPU_CONTROL_SITES_SERVICE_TOKEN": "s" * 43,
            "CPU_WORKLOAD_REPOSITORY": "Unjuno/gpu-control",
            "CPU_WORKLOAD_SOURCE_SHA": "a" * 40,
            "CPU_WORKLOAD_IMAGE_DIGEST": "sha256:" + "b" * 64,
        }

    def test_site_origin_is_normalized_and_rejects_ambiguous_urls(self):
        with patch.dict(os.environ, self.env, clear=False), patch.object(runner.shutil, "which", return_value="/usr/bin/docker"):
            self.assertEqual(runner.config()["origin"], "https://gpu-control.example")

        for origin in (
            "http://gpu-control.example",
            "https://user:pass@gpu-control.example",
            "https://gpu-control.example/unexpected-path",
            "https://gpu-control.example/?redirect=elsewhere",
            "https://gpu-control.example:444",
        ):
            with self.subTest(origin=origin), patch.dict(os.environ, {**self.env, "GPU_CONTROL_SITE_URL": origin}, clear=False), patch.object(runner.shutil, "which", return_value="/usr/bin/docker"):
                with self.assertRaisesRegex(runner.RunnerError, "CONFIGURATION_INVALID"):
                    runner.config()

    def test_sites_service_token_is_validated_as_opaque_bearer(self):
        with patch.dict(os.environ, {**self.env, "GPU_CONTROL_SITES_SERVICE_TOKEN": "A" * 43}, clear=False), patch.object(runner.shutil, "which", return_value="/usr/bin/docker"):
            self.assertEqual(runner.config()["sites_token"], "A" * 43)
        with patch.dict(os.environ, {**self.env, "GPU_CONTROL_SITES_SERVICE_TOKEN": "bad\r\nInjected: yes"}, clear=False), patch.object(runner.shutil, "which", return_value="/usr/bin/docker"):
            with self.assertRaisesRegex(runner.RunnerError, "CONFIGURATION_INVALID"):
                runner.config()

    def test_redirect_handler_refuses_redirect_target(self):
        handler = runner.RejectRedirects()
        self.assertIsNone(handler.redirect_request(None, None, 307, "Temporary Redirect", {}, "https://attacker.example"))

    def test_post_installs_redirect_rejection_handler(self):
        opener = Mock()
        opener.open.side_effect = URLError("redirect rejected")
        cfg = {"origin": "https://gpu-control.example", "runner_token": "r" * 48,
               "sites_token": "s" * 43}
        with patch.object(runner.urllib.request, "build_opener", return_value=opener) as build_opener:
            with self.assertRaisesRegex(runner.RunnerError, "SITE_REQUEST_FAILED"):
                runner.post(cfg, "/runner/claim")
        build_opener.assert_called_once_with(runner.RejectRedirects)
        sent = opener.open.call_args.args[0]
        self.assertEqual(sent.get_header("Authorization"), "Bearer " + cfg["runner_token"])
        self.assertEqual(sent.get_header("Oai-sites-authorization"), "Bearer " + cfg["sites_token"])


if __name__ == "__main__":
    unittest.main()
