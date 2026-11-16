#!/usr/bin/env bash
# Verify unit syntax and dependencies from disposable copies only.
# This helper never changes host accounts, /etc, /opt, or systemd state.
set -euo pipefail

if ! command -v systemd-analyze >/dev/null 2>&1; then
  echo "systemd-analyze is required on the Ubuntu CI runner" >&2
  exit 2
fi

root=$(mktemp -d /tmp/gpu-control-systemd-verify.XXXXXX)
trap 'rm -rf -- "$root"' EXIT
unit_dir="$root/units"
environment_file="$root/environment-placeholder"
mkdir -p "$unit_dir" "$root/workdir" "$root/var/lib"
: > "$environment_file"

for unit in gpu-control-api.service gpu-control-worker.service \
            gpu-control-supervisor.service gpu-control-db-check.service \
            gpu-control-db-migrate.service gpu-control-artifact-capacity.service \
            gpu-control-artifact-capacity.timer gpu-control-capacity-bridge.service; do
  copy="$unit_dir/$unit"
  install -D -m 0644 "deploy/$unit" "$copy"
  # The production paths and identities exist only on a configured host.
  # Substitute inert paths in this copy while preserving parsed arguments and
  # unit syntax; test_deploy_units.py checks the production directives.
  sed -E -i \
    -e "s#^(ExecStartPre|ExecStart)=[^[:space:]]+#\\1=/usr/bin/true#" \
    -e "s#^WorkingDirectory=.*#WorkingDirectory=$root/workdir#" \
    -e "s#^EnvironmentFile=-?.*#EnvironmentFile=$environment_file#" \
    -e "s#^(ReadOnlyPaths|ReadWritePaths)=.*#\\1=$root/var/lib#" \
    "$copy"
  systemd-analyze verify "$copy:$unit"
done
