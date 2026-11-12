"""Trusted harness. Workload code is imported ONLY inside the isolated container."""
import importlib.util
import json
import runpy
import sys
from pathlib import Path


def run(source: Path) -> dict | None:
    config = json.loads((source / ".execution.json").read_text())
    if config["profile"] == "python-script-v1":
        path = source / config["entrypoint"]
        sys.path.insert(0, str(source))
        sys.argv = [str(path), *config.get("args", [])]
        runpy.run_path(str(path), run_name="__main__")
        return None
    if config["profile"] != "orbitune-vocab-v1":
        raise RuntimeError("unknown_registered_profile")
    spec = importlib.util.spec_from_file_location("checked_vocab", source / "orbitune/tokenizer/vocab.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("missing_source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    vocab = module.TheoryRemiVocab()
    if len(vocab) != 204 or len(set(vocab.tokens)) != 204:
        raise RuntimeError("vocabulary_contract_changed")
    samples = [
        ["BAR", "POSITION_0", "NOTE_PITCH_60", "NOTE_DURATION_4", "VELOCITY_16"],
        ["NOTE_PITCH_21", "NOTE_PITCH_108", "POSITION_15", "NOTE_DURATION_64", "VELOCITY_32"],
        [],
    ]
    checks = 0
    for tokens in samples:
        if vocab.decode(vocab.encode(tokens)) != tokens:
            raise RuntimeError("roundtrip_failed")
        checks += 1
    for invalid in (-1, len(vocab)):
        try:
            vocab.decode([invalid])
        except ValueError:
            checks += 1
        else:
            raise RuntimeError("invalid_id_not_rejected")
    try:
        vocab.encode(["NOT_A_TOKEN"])
    except ValueError:
        checks += 1
    else:
        raise RuntimeError("unknown_token_not_rejected")
    return {"check": "tokenizer-roundtrip-v1", "status": "passed", "metrics": {"checks": checks, "vocab_size": len(vocab)}, "gpu_used": False}


if __name__ == "__main__":
    result = run(Path("/source"))
    if result is not None:
        print(json.dumps(result, allow_nan=False))
