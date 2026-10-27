"""Shared immutable Docker isolation options for both CPU execution lanes."""


def container_hardening_args() -> list[str]:
    return ["--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "10001:10001",
            "--pids-limit", "32", "--memory", "256m", "--cpus", "1"]
