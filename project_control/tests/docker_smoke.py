"""Real Docker contract check, run in CI; no provider credentials or GPU."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from project_control.runner import execute

CODE = '''import json, os, socket
assert os.getuid() == 10001
assert not any(k in os.environ for k in ("GITHUB_TOKEN", "MODAL_TOKEN_SECRET", "RUNPOD_API_KEY"))
assert not os.path.exists("/var/run/docker.sock")
try:
    socket.create_connection(("1.1.1.1", 443), timeout=0.2)
except OSError:
    pass
else:
    raise RuntimeError("network_not_blocked")
x = 8.0
initial = (x - 3.0) ** 2
for _ in range(10):
    x -= 0.2 * 2 * (x - 3.0)
final = (x - 3.0) ** 2
assert final < initial
print(json.dumps({"check":"script-contract-v1", "status":"passed", "gpu_used":False,
                  "metrics":{"initial_loss":initial,"final_loss":final}}))
'''
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory); source.chmod(0o755)
    (source / "smoke.py").write_text(CODE)
    entry = {"profile":"python-script-v1", "entrypoint":"smoke.py", "args":[], "check":"script-contract-v1"}
    (source / ".execution.json").write_text(json.dumps(entry))
    result = execute(source, "project-contract-ci", entry)
    assert result["values"]["final_loss"] < result["values"]["initial_loss"]
    print(json.dumps(result))
