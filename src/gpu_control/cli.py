from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import json
import sys

from .policy import PolicyError, load_policy, validate_against_policy
from .validation import ValidationError, build_request


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported value: {type(value)!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gpu-control")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a workload request without launching GPU resources")
    validate.add_argument("--target-repo", required=True)
    validate.add_argument("--target-sha", required=True)
    validate.add_argument("--dockerfile-path", default="Dockerfile")
    validate.add_argument("--gpu-profile", required=True)
    validate.add_argument("--max-runtime-minutes", required=True)
    validate.add_argument("--max-cost-usd", required=True)
    validate.add_argument("--policy", default="policies/gpu-policy.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "validate":
        try:
            request = build_request(
                target_repo=args.target_repo,
                target_sha=args.target_sha,
                dockerfile_path=args.dockerfile_path,
                gpu_profile=args.gpu_profile,
                max_runtime_minutes=args.max_runtime_minutes,
                max_cost_usd=args.max_cost_usd,
            )
            policy = load_policy(args.policy)
            effective_policy = validate_against_policy(request, policy)
        except (ValidationError, PolicyError, OSError, ValueError) as exc:
            print(json.dumps({"status": "rejected", "error": str(exc)}, sort_keys=True))
            return 2

        print(
            json.dumps(
                {
                    "status": "valid",
                    "dry_run": True,
                    "request": asdict(request),
                    "effective_policy": effective_policy,
                },
                default=_json_default,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
