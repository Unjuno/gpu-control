from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_current_documentation_matches_selected_workload() -> None:
    state = yaml.safe_load((ROOT / 'policies/repository-state.yaml').read_text(encoding='utf-8'))
    workload = state['active_workload']
    for path in ['README.md', 'docs/PARKED_MODE.md', 'docs/ORBITUNE_CANARY_ACCEPTANCE.md']:
        text = (ROOT / path).read_text(encoding='utf-8')
        assert workload['repository'] in text
        assert workload['source_sha'] in text
    assert workload['source_ci']['completion_protocol'] in (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'RunPodV1Adapter' in (ROOT / 'README.md').read_text(encoding='utf-8')


def test_audit_never_activates_paid_workflows() -> None:
    state = yaml.safe_load((ROOT / 'policies/repository-state.yaml').read_text(encoding='utf-8'))
    assert state['mode'] == 'parked'
    assert all(value is False for value in state['while_parked'].values())
    assert not (ROOT / '.github/workflows/paid-runpod.yml').exists()
