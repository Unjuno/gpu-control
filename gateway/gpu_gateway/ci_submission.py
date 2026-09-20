"""A comment is not activation of the parked paid-compute path.

The demo queue may be exercised. Any real provider, including future providers,
remains unavailable through this ingress until a separately reviewed activation.
Cancel, observation and result collection must remain available.
"""


def demo_submission_only(run: dict) -> bool:
    return isinstance(run, dict) and isinstance(run.get("plan"), dict) and run["plan"].get("provider") == "demo"
