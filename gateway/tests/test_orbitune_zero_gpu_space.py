from pathlib import Path


def test_zero_gpu_space_source_has_fixed_gpu_and_private_artifact_contract():
    workload = (Path(__file__).parents[2] / "sites" / "gpu-control-sites" / "modal"
                / "provider_runtime" / "workloads" / "orbitune-zero-gpu-eval")
    source = (workload / "app.py").read_text()
    readme = (workload / "README.md").read_text()
    requirements = [line for line in
                    (workload / "requirements.txt").read_text().splitlines() if line]

    assert '@spaces.GPU(duration=60, size="large")' in source
    assert 'api_name="evaluate"' in source
    assert 'api_name="status"' in source
    assert 'api_name="cancel"' in source
    assert "HF_READ_TOKEN" in source
    assert "HF_TOKEN" not in source
    assert "artifact_sha256" in source
    assert "torch.cuda.is_available()" in source
    assert "OrbituneGPT.load_checkpoint" in source
    assert 'label="request_id"' in source
    assert 'label="parameters_json"' in source
    assert 'label="source_sha"' in source
    assert 'label="result"' in source
    assert "sdk_version: 6.32.0" in readme
    assert "python_version: 3.12.12" in readme
    assert requirements == ["spaces==0.52.1", "huggingface_hub==2.4.0"]


def test_worker_image_disables_client_telemetry():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile.worker").read_text()
    modal_worker = (Path(__file__).parents[1] / "modal_worker.py").read_text()

    assert "GRADIO_ANALYTICS_ENABLED=False" in dockerfile
    assert "HF_HUB_DISABLE_TELEMETRY=1" in dockerfile
    assert "'GRADIO_ANALYTICS_ENABLED': 'False'" in modal_worker
    assert "'HF_HUB_DISABLE_TELEMETRY': '1'" in modal_worker
