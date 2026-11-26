"""Materialize a pinned commit from a previously fetched local Git object store.

Fetching and authorizing repositories are the caller's responsibility. This
module does not execute the source or provide container isolation.
"""
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


def stage_commit(repository, commit, destination, *, max_bytes=268435456, max_files=20000):
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("invalid_commit")
    if type(max_bytes) is not int or max_bytes < 1 or type(max_files) is not int or max_files < 1:
        raise ValueError("invalid_limits")
    source = Path(repository).resolve(strict=True)
    target = Path(destination)
    # An existing directory could contain symlinks planted by another process.
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    env = {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    git = shutil.which("git")
    if git is None:
        shutil.rmtree(target)
        raise ValueError("git_unavailable")
    process = subprocess.Popen([git, "-C", os.fspath(source), "archive", "--format=tar", commit],
                               env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    total = count = 0
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or not path.parts or
                        any(part in (".", "..") for part in path.parts) or
                        not (member.isfile() or member.isdir())):
                    raise ValueError("unsafe_archive_entry")
                count += 1
                total += member.size
                if count > max_files or total > max_bytes:
                    raise ValueError("source_limit_exceeded")
                output = target.joinpath(*path.parts)
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as src, output.open("xb") as dst:
                        while chunk := src.read(65536):
                            dst.write(chunk)
                    output.chmod(0o755 if member.mode & 0o111 else 0o644)
        if process.wait(timeout=5) != 0:
            raise ValueError("commit_unavailable")
    except tarfile.ReadError as exc:
        shutil.rmtree(target)
        raise ValueError("commit_unavailable") from exc
    except Exception:
        shutil.rmtree(target)
        raise
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
    return {"commit": commit, "files": count, "bytes": total}
