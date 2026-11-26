"""Fetch an exact commit from a public GitHub repository into a fresh store.

Call only from a resource-limited source-staging environment with network
access restricted to GitHub. This module does not sandbox Git or workload code.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path


def fetch_public_commit(repository, commit, destination, *, timeout=120, _run=subprocess.run):
    if (not isinstance(repository, str) or
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repository) is None or
            repository.split("/")[1] in (".", "..") or
            not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None or
            type(timeout) is not int or not 1 <= timeout <= 300):
        raise ValueError("invalid_source")
    git = shutil.which("git")
    if git is None:
        raise ValueError("git_unavailable")
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "https", "LC_ALL": "C"}
    common = [git, "-c", "http.followRedirects=false", "-c", "protocol.file.allow=never"]
    def invoke(args):
        return _run(common + args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, check=True, timeout=timeout).stdout
    try:
        invoke(["init", "--bare", os.fspath(destination)])
        invoke(["-C", os.fspath(destination), "fetch", "--no-tags", "--depth=1", "--",
                f"https://github.com/{repository}.git", commit])
        actual = invoke(["-C", os.fspath(destination), "rev-parse", "--verify", "FETCH_HEAD^{commit}"])
        if actual.strip() != commit.encode("ascii"):
            raise ValueError("commit_mismatch")
    except Exception:
        shutil.rmtree(destination)
        raise
    return {"repository": repository.lower(), "commit": commit, "store": os.fspath(destination)}
