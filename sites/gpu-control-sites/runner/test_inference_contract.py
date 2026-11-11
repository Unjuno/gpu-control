import hashlib
import json
import unittest
from unittest.mock import patch

import run


def configured_run(parameters=None, runtime_seconds=30):
    return {
        "id": "a" * 32,
        "lease_id": "b" * 32,
        "fingerprint": "c" * 64,
        "workload": run.WORKLOAD,
        "repository": "Unjuno/gpu-control",
        "source_sha": "d" * 40,
        "image_digest": "sha256:" + "e" * 64,
        "runtime_seconds": runtime_seconds,
        "parameters": parameters or {"prompt": "Once upon a time", "max_new_tokens": 12, "seed": 61112},
    }


def result_for(experiment, model_sha=run.MODEL_SHA256):
    prompt = experiment["parameters"]["prompt"]
    metrics = {
        "elapsed_ms": 150,
        "generated_text": prompt + " there was a little girl",
        "generated_tokens": 6,
        "max_new_tokens": experiment["parameters"]["max_new_tokens"],
        "model_id": run.MODEL_ID,
        "model_sha256": model_sha,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "seed": experiment["parameters"]["seed"],
        "temperature": run.TEMPERATURE,
    }
    identity = {"run_id": experiment["id"], "source_sha": experiment["source_sha"],
                "plan_fingerprint": experiment["fingerprint"], "metrics": metrics}
    checksum = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return {"schema_version": 1, "run_id": experiment["id"], "source_sha": experiment["source_sha"],
            "plan_fingerprint": experiment["fingerprint"], "check": run.WORKLOAD,
            "status": "passed", "gpu_used": False, "checks": run.CHECKS,
            "metrics": metrics, "checksum": checksum}


class InferenceContractTests(unittest.TestCase):
    def test_runner_keeps_fixed_isolation_and_forwards_only_bounded_parameters(self):
        experiment = configured_run()
        args, name = run.start_args(experiment, {
            "repository": experiment["repository"], "source_sha": experiment["source_sha"],
            "image_digest": experiment["image_digest"],
        })
        self.assertEqual(name, "gpu-control-" + experiment["id"])
        self.assertIn("none", args)
        self.assertIn("--read-only", args)
        self.assertIn("10001:10001", args)
        self.assertIn("256m", args)
        self.assertNotIn("-m", args)
        self.assertNotIn("--publish", args)
        parameters = next(value.split("=", 1)[1] for value in args if value.startswith("GPU_CONTROL_PARAMETERS_JSON="))
        self.assertEqual(json.loads(parameters), experiment["parameters"])

    def test_runner_rejects_extra_or_oversized_prompt_parameters(self):
        base = {"repository": "Unjuno/gpu-control", "source_sha": "d" * 40,
                "image_digest": "sha256:" + "e" * 64}
        for parameters in (
            {"prompt": "x" * 129, "max_new_tokens": 12, "seed": 1},
            {"prompt": "safe", "max_new_tokens": 12, "seed": 1, "iterations": 1},
        ):
            with self.subTest(parameters=parameters):
                with self.assertRaises(run.RunnerError):
                    run.start_args(configured_run(parameters), base)

    def test_runner_accepts_model_bound_inference_result_and_checksum(self):
        experiment = configured_run()
        receipt = json.dumps(result_for(experiment), separators=(",", ":")).encode()
        def fake_docker(args, timeout=15, allow_error=False):
            if args[0] == "inspect":
                return b'{"Running":false,"ExitCode":0}'
            if args[0] == "logs":
                return receipt
            raise AssertionError(args)
        with patch.object(run, "docker", side_effect=fake_docker):
            status, result = run.wait_result(experiment, {}, "f" * 12)
        self.assertEqual(status, "passed")
        self.assertTrue(result["metrics"]["generated_text"].startswith(experiment["parameters"]["prompt"]))
        self.assertEqual(result["metrics"]["model_sha256"], run.MODEL_SHA256)

    def test_runner_rejects_result_from_another_model_checkpoint(self):
        experiment = configured_run()
        receipt = json.dumps(result_for(experiment, model_sha="0" * 64), separators=(",", ":")).encode()
        def fake_docker(args, timeout=15, allow_error=False):
            if args[0] == "inspect":
                return b'{"Running":false,"ExitCode":0}'
            if args[0] == "logs":
                return receipt
            raise AssertionError(args)
        with patch.object(run, "docker", side_effect=fake_docker):
            status, result = run.wait_result(experiment, {}, "f" * 12)
        self.assertEqual(status, "failed")
        self.assertEqual(result, {"failure_code": "workload_output_invalid"})

    def test_runner_rejects_malformed_unicode_without_crashing(self):
        experiment = configured_run()
        result = result_for(experiment)
        result["metrics"]["generated_text"] += "\ud800"
        identity = {"run_id": experiment["id"], "source_sha": experiment["source_sha"],
                    "plan_fingerprint": experiment["fingerprint"], "metrics": result["metrics"]}
        result["checksum"] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode("utf-8", "surrogatepass")).hexdigest()
        receipt = json.dumps(result, separators=(",", ":")).encode()
        def fake_docker(args, timeout=15, allow_error=False):
            if args[0] == "inspect":
                return b'{"Running":false,"ExitCode":0}'
            if args[0] == "logs":
                return receipt
            raise AssertionError(args)
        with patch.object(run, "docker", side_effect=fake_docker):
            status, value = run.wait_result(experiment, {}, "f" * 12)
        self.assertEqual(status, "failed")
        self.assertEqual(value, {"failure_code": "workload_output_invalid"})


if __name__ == "__main__":
    unittest.main()
