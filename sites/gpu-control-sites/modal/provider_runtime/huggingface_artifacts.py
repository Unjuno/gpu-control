"""Private, immutable Hugging Face Hub artifact publication boundary."""
from __future__ import annotations

import hashlib
import importlib
from pathlib import Path, PurePosixPath
import re
from typing import Any, Callable

from .settings import ProviderSettings


_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class HuggingFaceArtifactStore:
    """Upload on a trusted worker and verify by immutable commit re-download.

    The returned reference is deliberately credential-free and can safely be
    persisted in a run result.  Kaggle never receives the Hub write token.
    """

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        api: Any = None,
        downloader: Callable[..., str] | None = None,
        max_bytes: int = 20 * 1024 * 1024 * 1024,
    ) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("Hugging Face artifact size limit must be positive")
        self.settings = settings
        self.max_bytes = max_bytes
        if api is None or downloader is None:
            hub = importlib.import_module("huggingface_hub")
            api = api or hub.HfApi(token=settings.hf_artifact_write_token)
            downloader = downloader or hub.hf_hub_download
        self.api = api
        self.downloader = downloader

    def _verify_private_revision(self, repo_id: str, revision: str) -> None:
        try:
            info = self.api.repo_info(
                repo_id=repo_id, repo_type="model", revision=revision,
                token=self.settings.hf_artifact_write_token,
            )
        except Exception as exc:
            raise RuntimeError("immutable Hugging Face artifact revision is unavailable") from exc
        if getattr(info, "private", None) is not True or getattr(info, "sha", None) != revision:
            raise RuntimeError("Hugging Face artifact revision is not exact and private")

    @staticmethod
    def _remote_path(path_in_repo: str) -> str:
        if not isinstance(path_in_repo, str) or not path_in_repo or len(path_in_repo) > 512:
            raise ValueError("Hugging Face artifact path is invalid")
        path = PurePosixPath(path_in_repo)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Hugging Face artifact path must be canonical and relative")
        if any(ord(character) < 32 or ord(character) == 127 for character in path_in_repo):
            raise ValueError("Hugging Face artifact path contains control characters")
        return str(path)

    def publish(
        self,
        artifact_path: str | Path,
        *,
        repo_id: str,
        path_in_repo: str,
        run_id: str,
        source_sha: str,
    ) -> dict[str, object]:
        if not self.settings.hf_artifact_write_token:
            raise RuntimeError("Hugging Face worker token is not configured")
        if (_REPO_RE.fullmatch(repo_id or "") is None or
                repo_id not in self.settings.hf_artifact_repositories):
            raise ValueError("Hugging Face repository is not allowlisted")
        if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id) is None:
            raise ValueError("artifact run id is invalid")
        if not isinstance(source_sha, str) or _SHA40_RE.fullmatch(source_sha) is None:
            raise ValueError("artifact source SHA is invalid")
        remote_path = self._remote_path(path_in_repo)
        local_path = Path(artifact_path)
        if local_path.is_symlink() or not local_path.is_file():
            raise ValueError("artifact must be a regular non-symlink file")
        size = local_path.stat().st_size
        if size < 1 or size > self.max_bytes:
            raise ValueError("artifact size exceeds the configured bound")
        info = self.api.repo_info(
            repo_id=repo_id, repo_type="model", token=self.settings.hf_artifact_write_token,
        )
        if getattr(info, "private", None) is not True:
            raise ValueError("Hugging Face artifact repository must be private")
        checksum = _sha256(local_path)
        exists = self.api.file_exists(
            repo_id=repo_id, filename=remote_path, repo_type="model",
            token=self.settings.hf_artifact_write_token,
        )
        if type(exists) is not bool:
            raise RuntimeError("Hugging Face file existence result is invalid")
        if exists:
            revision = getattr(info, "sha", None)
            if not isinstance(revision, str) or _SHA40_RE.fullmatch(revision) is None:
                raise RuntimeError("Hugging Face repository did not return an immutable revision")
            existing = Path(self.downloader(
                repo_id=repo_id, filename=remote_path, repo_type="model",
                revision=revision, token=self.settings.hf_artifact_write_token,
            ))
            if not existing.is_file() or _sha256(existing) != checksum:
                raise RuntimeError("immutable artifact path already contains different content")
        else:
            commit = self.api.upload_file(
                path_or_fileobj=str(local_path),
                path_in_repo=remote_path,
                repo_id=repo_id,
                repo_type="model",
                token=self.settings.hf_artifact_write_token,
                commit_message=f"gpu-control artifact {run_id}",
            )
            revision = getattr(commit, "oid", None)
        if not isinstance(revision, str) or _SHA40_RE.fullmatch(revision) is None:
            raise RuntimeError("Hugging Face upload did not return an immutable revision")
        self._verify_private_revision(repo_id, revision)
        downloaded = Path(self.downloader(
            repo_id=repo_id,
            filename=remote_path,
            repo_type="model",
            revision=revision,
            token=self.settings.hf_artifact_write_token,
        ))
        if not downloaded.is_file() or _sha256(downloaded) != checksum:
            raise RuntimeError("Hugging Face artifact re-download checksum mismatch")
        self._verify_private_revision(repo_id, revision)
        return {
            "service": "huggingface_hub",
            "repo_id": repo_id,
            "repo_type": "model",
            "path_in_repo": remote_path,
            "revision": revision,
            "sha256": checksum,
            "size_bytes": size,
            "run_id": run_id,
            "source_sha": source_sha,
            "private": True,
        }
