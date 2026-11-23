from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

import pytest

from gpu_gateway.kaggle_bridge import exact_status, latest_snapshot


class FakeApi:
    def __init__(self, kernels=(), statuses=None):
        self.kernels = list(kernels)
        self.statuses = statuses or {}
        self.status_calls = []

    def kernels_list(self, **kwargs):
        assert kwargs == {
            "mine": True, "user": "owner", "search": "kernel", "page_size": 100,
        }
        return self.kernels

    def kernels_status(self, kernel):
        self.status_calls.append(kernel)
        return self.statuses[kernel]


def response(status="running", message=None):
    return SimpleNamespace(status=status, failure_message=message)


class ProviderStatus(Enum):
    RUNNING = 1


def test_latest_snapshot_returns_exact_version_and_status():
    api = FakeApi(
        kernels=[SimpleNamespace(ref="owner/kernel", current_version_number=8)],
        statuses={"owner/kernel/8": response()},
    )

    assert latest_snapshot(api, "owner/kernel") == {
        "versionNumber": 8, "status": "running", "failureMessage": None,
    }
    assert api.status_calls == ["owner/kernel/8"]


def test_latest_snapshot_reports_missing_without_status_call():
    api = FakeApi(kernels=[SimpleNamespace(ref="owner/other", current_version_number=3)])
    assert latest_snapshot(api, "owner/kernel") == {
        "versionNumber": 0, "status": "missing", "failureMessage": None,
    }
    assert api.status_calls == []


def test_exact_status_is_bound_to_requested_version():
    api = FakeApi(statuses={"owner/kernel/7": response("error", "failed")})
    assert exact_status(api, "owner/kernel/7") == {
        "versionNumber": 7, "status": "error", "failureMessage": "failed",
    }


def test_status_normalizes_official_sdk_enum():
    api = FakeApi(statuses={"owner/kernel/7": response(ProviderStatus.RUNNING, "")})
    assert exact_status(api, "owner/kernel/7") == {
        "versionNumber": 7, "status": "running", "failureMessage": None,
    }


@pytest.mark.parametrize("kernel", ["", "owner", "owner/kernel/1", "../kernel"])
def test_latest_snapshot_rejects_noncanonical_identity(kernel):
    with pytest.raises(ValueError):
        latest_snapshot(FakeApi(), kernel)


@pytest.mark.parametrize("kernel", ["owner/kernel", "owner/kernel/0", "owner/kernel/latest"])
def test_exact_status_rejects_unversioned_identity(kernel):
    with pytest.raises(ValueError):
        exact_status(FakeApi(), kernel)
