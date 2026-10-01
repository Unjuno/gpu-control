"""Offline acceptance of an installed CLI outside its source tree. Never calls a provider."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def check(executable: Path) -> list[str]:
    executable = executable.resolve(strict=True)
    checks: list[str] = []
    # Deliberately do not pass provider/GitHub credentials or PYTHONPATH to the CLI.
    env = {name: os.environ[name] for name in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if name in os.environ}
    with tempfile.TemporaryDirectory(prefix='gpu-control-acceptance-') as temp:
        env['HOME'] = temp
        env['USERPROFILE'] = temp

        def run(arguments: list[str], expected_code: int) -> dict[str, object]:
            result = subprocess.run([str(executable), *arguments], cwd=temp, env=env,
                                    text=True, capture_output=True, timeout=30, check=False)
            if result.returncode != expected_code:
                raise RuntimeError(f'CLI exit {result.returncode}, expected {expected_code}: {arguments}')
            if 'Traceback' in result.stderr:
                raise RuntimeError('CLI produced a traceback')
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                raise RuntimeError('CLI output was not a JSON object')
            return payload

        for command in ('self-test', 'provider-self-test'):
            result = run([command], 0)
            assert result['status'] == 'ok' and result['dry_run'] is True
            if command == 'provider-self-test':
                assert result['provider'] == 'synthetic'
                assert result['external_resources_created'] is False
                assert result['billable_compute'] is False
            checks.append(command)
        base = ['validate', '--target-repo', 'example/model', '--target-sha', 'a' * 40,
                '--dockerfile-path', 'Dockerfile', '--gpu-profile', 'cheap-24gb',
                '--max-runtime-minutes', '5', '--max-cost-usd', '0.05']
        valid = run(base, 0)
        assert valid['status'] == 'valid' and valid['dry_run'] is True
        checks.append('valid-request')
        for option, value in [('--target-sha', 'main'), ('--dockerfile-path', '../Dockerfile'),
                              ('--dockerfile-path', './Dockerfile'), ('--max-runtime-minutes', '1.5'),
                              ('--max-runtime-minutes', '999999'), ('--max-cost-usd', '1e100'),
                              ('--max-cost-usd', '0.001'), ('--gpu-profile', 'unapproved')]:
            args = list(base)
            args[args.index(option) + 1] = value
            assert run(args, 2)['status'] == 'rejected'
            checks.append(f'reject:{option}:{value}')
        bad_policy = Path(temp) / 'invalid.yaml'
        for text in ['hard_limits: [\n', 'version: 1\nversion: 2\n']:
            bad_policy.write_text(text, encoding='utf-8')
            assert run([*base, '--policy', str(bad_policy)], 2)['status'] == 'rejected'
            checks.append('reject-invalid-policy')
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path, help='Absolute path to the installed gpu-control executable')
    args = parser.parse_args()
    try:
        checks = check(args.executable)
    except (AssertionError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}))
        return 1
    print(json.dumps({'status': 'PASS', 'checks': checks, 'network_or_gpu_required': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
