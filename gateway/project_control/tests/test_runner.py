import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from project_control import runner as r


class Tests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / "policy.json").read_text())
        self.request = {"repository": "Unjuno/orbitune", "sha": "a" * 40, "workload": "orbitune-tokenizer"}
        self.env = {"GITHUB_EVENT_NAME": "issue_comment", "GITHUB_REPOSITORY": "Unjuno/gpu-control",
                    "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_ACTOR_ID": "241447786",
                    "GITHUB_SHA": "b" * 40, "GITHUB_RUN_ID": "1234"}
        self.event = {"action": "created", "repository": {"id": 1342703665, "owner": {"id": 241447786}},
                      "sender": {"id": 241447786}, "issue": {"number": 48, "state": "open"},
                      "comment": {"id": 25, "user": {"id": 241447786, "type": "User"},
                                  "created_at": "2026-09-21T00:00:00Z", "updated_at": "2026-09-21T00:00:00Z",
                                  "body": "/gpu check\n" + json.dumps(self.request)}}

    def test_owner_account_admitted(self):
        self.assertEqual(r.validate_event(self.event, self.env, self.policy), self.request)

    def test_untrusted_actor_rejected(self):
        for key in ("sender", "comment"):
            event = copy.deepcopy(self.event)
            if key == "sender": event[key]["id"] = 42
            else: event[key]["user"]["id"] = 42
            with self.subTest(key=key), self.assertRaises(r.Rejected):
                r.validate_event(event, self.env, self.policy)

    def test_reruns_other_branches_and_wrong_identity_rejected(self):
        for key, value in {"GITHUB_REF": "refs/pull/99/merge", "GITHUB_RUN_ATTEMPT": "2",
                           "GITHUB_ACTOR_ID": "42", "GITHUB_EVENT_NAME": "pull_request_target",
                           "GITHUB_SHA": "main", "GITHUB_RUN_ID": "1;echo wrong"}.items():
            with self.subTest(key=key), self.assertRaises(r.Rejected):
                r.validate_event(self.event, dict(self.env, **{key: value}), self.policy)

    def test_pr_comments_closed_issues_and_edits_rejected(self):
        changes = [("issue", "pull_request", {}), ("issue", "state", "closed"),
                   ("issue", "number", 49), ("comment", "updated_at", "2026-09-21T00:00:01Z")]
        for obj, key, value in changes:
            event = copy.deepcopy(self.event); event[obj][key] = value
            with self.subTest(key=key), self.assertRaises(r.Rejected):
                r.validate_event(event, self.env, self.policy)

    def test_input_schema(self):
        bad = ["/gpu check\n[]", "/gpu check\n{}", "/gpu check\n{\"sha\":\"a\",\"sha\":\"b\"}",
               "/gpu run\n{}", "/gpu check\n{\"x\":NaN}", "/gpu check\n" + "x" * 4100]
        for body in bad:
            with self.subTest(body=body[:40]), self.assertRaises(r.Rejected):
                r.parse_request(body, self.policy)
        for values in ({"sha": "main"}, {"sha": "a" * 39}, {"sha": True},
                       {"repository": "someone/repo"}, {"command": "rm -rf /"}, {"workload": "unknown"}):
            with self.subTest(values=values), self.assertRaises(r.Rejected):
                r.parse_request("/gpu check\n" + json.dumps(dict(self.request, **values)), self.policy)

    def get_api(self, *, private=False, owner=241447786, sha=None, symlink=False, corrupt=False, payload=b"x = 1\n"):
        blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
        def get(path):
            if path == "/repos/Unjuno/orbitune":
                return {"id": 1338946604, "owner": {"id": owner}, "private": private}
            if "/commits/" in path: return {"sha": sha or self.request["sha"]}
            if "/contents/" in path:
                data = {"type": "file", "encoding": "base64", "content": base64.b64encode(payload).decode(),
                        "sha": "0" * 40 if corrupt else blob}
                if symlink: data["target"] = "../../secret"
                return data
            raise AssertionError(path)
        return get

    def test_source_download_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            blobs = r.fetch_sources(self.request, self.policy, directory, self.get_api())
            self.assertIn("orbitune/tokenizer/vocab.py", blobs)
            self.assertTrue((Path(directory) / ".execution.json").exists())
            self.assertEqual((Path(directory) / "orbitune/tokenizer/vocab.py").read_bytes(), b"x = 1\n")

    def test_wrong_source_identity_and_private_files_rejected(self):
        for kwargs in ({"private": True}, {"owner": 42}, {"sha": "c" * 40}, {"corrupt": True}, {"symlink": True}, {"payload": b"x" * 131073}):
            with self.subTest(kwargs=str(kwargs)[:50]), tempfile.TemporaryDirectory() as directory, self.assertRaises(r.Rejected):
                r.fetch_sources(self.request, self.policy, directory, self.get_api(**kwargs))

    def test_no_source_overwrite_or_path_traversal(self):
        policy = copy.deepcopy(self.policy)
        policy["workloads"]["orbitune-tokenizer"]["files"] = ["../../elsewhere.py"]
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(r.Rejected):
            r.fetch_sources(self.request, policy, directory, self.get_api())
        with tempfile.TemporaryDirectory() as directory:
            r.fetch_sources(self.request, self.policy, directory, self.get_api())
            with self.assertRaises(r.Rejected):
                r.fetch_sources(self.request, self.policy, directory, self.get_api())

    def test_new_script_project_needs_registry_only(self):
        policy = copy.deepcopy(self.policy)
        policy["workloads"]["orbitune-tokenizer"].update(profile="python-script-v1", entrypoint="smoke.py", files=["smoke.py"], args=[])
        with tempfile.TemporaryDirectory() as directory:
            blobs = r.fetch_sources(self.request, policy, directory, self.get_api(payload=b"print('ok')\n"))
            self.assertEqual(list(blobs), ["smoke.py"])
        policy["workloads"]["orbitune-tokenizer"]["entrypoint"] = "outside.py"
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(r.Rejected):
            r.fetch_sources(self.request, policy, directory, self.get_api())

    def test_live_comment_binding(self):
        actual = copy.deepcopy(self.event["comment"])
        actual["issue_url"] = "https://api.github.com/repos/Unjuno/gpu-control/issues/48"
        def get(path): return self.event["issue"] if path.endswith("/issues/48") else actual
        now = r.datetime.fromisoformat("2026-09-21T00:00:02+00:00").timestamp()
        r.verify_live_comment(self.event, self.policy, get, now)
        actual["body"] += "changed"
        with self.assertRaises(r.Rejected): r.verify_live_comment(self.event, self.policy, get, now)

    def test_old_comment_not_replayed(self):
        actual = copy.deepcopy(self.event["comment"])
        actual["issue_url"] = "https://api.github.com/repos/Unjuno/gpu-control/issues/48"
        def get(path): return self.event["issue"] if path.endswith("/issues/48") else actual
        now = r.datetime.fromisoformat("2026-09-22T00:00:02+00:00").timestamp()
        with self.assertRaises(r.Rejected): r.verify_live_comment(self.event, self.policy, get, now)

    def test_docker_contract(self):
        args = r.container_args("sha256:" + "a" * 64, "/tmp/source", "check-123")
        for item in ("none", "--read-only", "ALL", "no-new-privileges", "10001:10001", "--pids-limit", "--memory", "--cpus"):
            self.assertIn(item, args)
        self.assertFalse(any("docker.sock" in a for a in args))
        self.assertNotIn("--privileged", args)
        self.assertNotIn("--gpus", args)
        self.assertNotIn("--env-file", args)
        self.assertIn("readonly", args[-2])
        with self.assertRaises(r.Rejected): r.container_args("image:latest", "/tmp/source", "check-123")

    def test_no_credential_forwarding(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "sentinel", "RUNPOD_API_KEY": "sentinel", "MODAL_TOKEN_SECRET": "sentinel"}):
            self.assertFalse(any("TOKEN" in key or "KEY" in key for key in r.clean_environment()))

    def test_bounded_process_success(self):
        code, raw = r.bounded_process([sys.executable, "-c", "print('fine')"])
        self.assertEqual((code, raw), (0, b"fine\n"))

    def test_bounded_process_overflow(self):
        with self.assertRaises(r.Rejected):
            r.bounded_process([sys.executable, "-c", "print('x' * 10000)"], limit=100)

    def test_bounded_process_timeout(self):
        with self.assertRaises(r.Rejected):
            r.bounded_process([sys.executable, "-c", "import time;time.sleep(5)"], seconds=0.1)

    def test_parked_gate_denies_every_real_provider(self):
        spec = importlib.util.spec_from_file_location("ci_submission", ROOT.parent / "gpu_gateway/ci_submission.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertTrue(module.demo_submission_only({"plan": {"provider": "demo"}}))
        for run in ({"plan": {"provider": "modal"}}, {"plan": {"provider": "runpod"}},
                    {"plan": {"provider": "future-provider"}}, {}, {"plan": None}):
            self.assertFalse(module.demo_submission_only(run))

    def test_fixed_api_no_untrusted_hosts(self):
        with self.assertRaises(r.Rejected): r.api("https://evil.example/")
        self.assertIsNone(r.NoRedirect().redirect_request(None, None, None, None, None, "https://example.org"))


if __name__ == "__main__":
    unittest.main()
