from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import json
import sys

from .policy import PolicyError, load_policy, validate_against_policy
from .validation import ValidationError, build_request


_SELF_TEST_SHA = "0123456789abcdef0123456789abcdef01234567"


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported value: {type(value)!r}")


def _validate_request(args: argparse.Namespace) -> dict[str, object]:
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
    return {
        "status": "valid",
        "dry_run": True,
        "request": asdict(request),
        "effective_policy": effective_policy,
    }


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
    validate.add_argument(
        "--policy",
        default=None,
        help="optional policy YAML path; omitted uses the policy bundled with gpu-control",
    )

    subparsers.add_parser(
        "self-test",
        help="verify the installed CLI and bundled policy without network or GPU access",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "validate":
            result = _validate_request(args)
        elif args.command == "self-test":
            request = build_request(
                target_repo="example/model",
                target_sha=_SELF_TEST_SHA,
                dockerfile_path="Dockerfile",
                gpu_profile="cheap-24gb",
                max_runtime_minutes=5,
                max_cost_usd="0.05",
            )
            effective_policy = validate_against_policy(request, load_policy())
            result = {
                "status": "ok",
                "dry_run": True,
                "checks": ["cli", "bundled_policy", "validation"],
                "effective_policy": effective_policy,
            }
        else:
            return 2
    except (ValidationError, PolicyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, default=_json_default, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
