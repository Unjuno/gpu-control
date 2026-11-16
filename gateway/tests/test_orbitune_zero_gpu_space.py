from pathlib import Path


def test_zero_gpu_space_source_has_fixed_gpu_and_private_artifact_contract():
    source = (Path(__file__).parents[1] / "workloads" / "orbitune-zero-gpu-eval" / "app.py").read_text()

    assert '@spaces.GPU(duration=60, size="large")' in source
    assert 'api_name="evaluate"' in source
    assert 'api_name="status"' in source
    assert 'api_name="cancel"' in source
    assert "HF_READ_TOKEN" in source
    assert "HF_TOKEN" not in source
    assert "artifact_sha256" in source
    assert "torch.cuda.is_available()" in source
    assert "OrbituneGPT.load_checkpoint" in source
