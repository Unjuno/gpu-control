#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dist_root="$project_root/dist"

node "$project_root/scripts/generate_workload_registry.mjs"
rm -rf "$dist_root"
mkdir -p "$dist_root/server" "$dist_root/.openai" "$dist_root/.openai/drizzle"
node "$project_root/scripts/copy-worker-runtime.mjs" "$project_root/worker" "$dist_root/server"
cp "$project_root/.openai/hosting.json" "$dist_root/.openai/hosting.json"
cp "$project_root"/drizzle/*.sql "$dist_root/.openai/drizzle/"

echo "Built $dist_root"
