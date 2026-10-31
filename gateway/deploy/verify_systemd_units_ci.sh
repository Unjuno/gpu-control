#!/usr/bin/env bash
# CI-only syntax/reference check. Run only on an ephemeral Ubuntu runner.
# It installs inert placeholders so systemd-analyze can resolve unit paths;
# it never starts a service, opens a network client, or reads real credentials.
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_OS:-}" != Linux ]]; then
  echo "This helper may run only on an ephemeral Linux GitHub Actions runner" >&2
  exit 2
fi

if ! command -v systemd-analyze >/dev/null 2>&1; then
  echo "systemd-analyze is required on the Ubuntu CI runner" >&2
  exit 2
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

ensure_group() {
  if ! getent group "$1" >/dev/null; then
    as_root groupadd --system "$1"
  fi
}

ensure_user() {
  local user="$1" group="$2"
  if ! id "$user" >/dev/null 2>&1; then
    as_root useradd --system --no-create-home --shell /usr/sbin/nologin --gid "$group" "$user"
  fi
}

ensure_group gpu-control-artifacts
ensure_group gpu-control-artifact-probes
ensure_group gpu-control-migrate
ensure_group gpu-control-capacity-bridge
ensure_group systemd-journal
ensure_group docker
ensure_user gpu-control-api gpu-control-artifacts
ensure_user gpu-control-worker gpu-control-artifacts
ensure_user gpu-control-migrate gpu-control-migrate
ensure_user gpu-control-capacity gpu-control-artifacts
ensure_user gpu-control-capacity-bridge gpu-control-capacity-bridge

as_root install -d -o root -g root -m 0750 /etc/gpu-control
for env_file in gateway.env api.env capacity.env worker-secrets.env; do
  as_root install -o root -g root -m 0600 /dev/null "/etc/gpu-control/$env_file"
done

as_root install -d -o root -g root -m 0755 \
  /opt/gpu-control/venv/bin /opt/gpu-control/gateway/deploy
for executable in /opt/gpu-control/venv/bin/uvicorn \
                  /opt/gpu-control/venv/bin/python \
                  /opt/gpu-control/gateway/deploy/check_artifact_capacity.py \
                  /opt/gpu-control/gateway/deploy/capacity_event_bridge.py; do
  as_root install -o root -g root -m 0755 /dev/null "$executable"
done

unit_dir=/etc/systemd/system
for unit in gpu-control-api.service gpu-control-worker.service \
            gpu-control-supervisor.service gpu-control-db-check.service \
            gpu-control-db-migrate.service \
            gpu-control-artifact-capacity.service gpu-control-artifact-capacity.timer \
            gpu-control-capacity-bridge.service; do
  as_root install -o root -g root -m 0644 "deploy/$unit" "$unit_dir/$unit"
done

as_root systemd-analyze verify \
  "$unit_dir/gpu-control-db-check.service" \
  "$unit_dir/gpu-control-db-migrate.service" \
  "$unit_dir/gpu-control-api.service" \
  "$unit_dir/gpu-control-worker.service" \
  "$unit_dir/gpu-control-supervisor.service" \
  "$unit_dir/gpu-control-artifact-capacity.service" \
  "$unit_dir/gpu-control-artifact-capacity.timer" \
  "$unit_dir/gpu-control-capacity-bridge.service"
