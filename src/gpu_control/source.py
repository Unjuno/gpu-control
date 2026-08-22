from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .validation import WorkloadRequest


_GITHUB_API = "https://api.github.com"


class SourceVerificationError(RuntimeError):
    """Raised when a workload source cannot be verified safely."""


@dataclass(frozen=True)
class SourceVerificationResult:
    repository: str
    commit_sha: str
    dockerfile_path: str
    repository_public: bool
    commit_verified: bool
    dockerfile_verified: bool


def _get_json(url: str, *, token: str | None, timeout: float) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gpu-control",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API origin
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            raise SourceVerificationError("GitHub source object was not found") from exc
        raise SourceVerificationError(f"GitHub API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise SourceVerificationError("GitHub API could not be reached") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceVerificationError("GitHub API returned an invalid response") from exc


def verify_public_github_source(
    request: WorkloadRequest,
    *,
    token: str | None = None,
    timeout: float = 10.0,
) -> SourceVerificationResult:
    """Verify repository visibility, exact commit identity, and Dockerfile existence.

    The public MVP intentionally accepts only public GitHub repositories. An optional
    token is used only to improve API reliability/rate limits; it does not expand the
    accepted trust model to private repositories.
    """

    if token is None:
        token = os.environ.get("GITHUB_TOKEN") or None

    owner, repository = request.target_repo.split("/", 1)
    repo_path = f"{quote(owner, safe='')}/{quote(repository, safe='')}"

    repo_data = _get_json(f"{_GITHUB_API}/repos/{repo_path}", token=token, timeout=timeout)
    if not isinstance(repo_data, dict):
        raise SourceVerificationError("GitHub repository response has an unexpected shape")
    if repo_data.get("private") is not False:
        raise SourceVerificationError("target repository must be public")
    if str(repo_data.get("full_name", "")).lower() != request.target_repo.lower():
        raise SourceVerificationError("GitHub repository identity did not match target_repo")

    commit_data = _get_json(
        f"{_GITHUB_API}/repos/{repo_path}/commits/{quote(request.target_sha, safe='')}",
        token=token,
        timeout=timeout,
    )
    if not isinstance(commit_data, dict):
        raise SourceVerificationError("GitHub commit response has an unexpected shape")
    resolved_sha = str(commit_data.get("sha", "")).lower()
    if resolved_sha != request.target_sha:
        raise SourceVerificationError("GitHub did not resolve the exact requested commit SHA")

    encoded_path = quote(request.dockerfile_path, safe="/")
    contents_data = _get_json(
        f"{_GITHUB_API}/repos/{repo_path}/contents/{encoded_path}?ref={quote(request.target_sha, safe='')}",
        token=token,
        timeout=timeout,
    )
    if not isinstance(contents_data, dict) or contents_data.get("type") != "file":
        raise SourceVerificationError("dockerfile_path does not resolve to a file at target_sha")

    return SourceVerificationResult(
        repository=request.target_repo,
        commit_sha=request.target_sha,
        dockerfile_path=request.dockerfile_path,
        repository_public=True,
        commit_verified=True,
        dockerfile_verified=True,
    )
