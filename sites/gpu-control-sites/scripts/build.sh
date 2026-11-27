#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dist_root="$project_root/dist"

node "$project_root/scripts/generate_workload_registry.mjs"
rm -rf "$dist_root"
mkdir -p "$dist_root/server" "$dist_root/.openai" "$dist_root/.openai/drizzle"
cp "$project_root/worker/index.js" "$dist_root/server/index.js"
cp "$project_root/worker/workload_registry.js" "$dist_root/server/workload_registry.js"
cp "$project_root/worker/gateway_delegation.js" "$dist_root/server/gateway_delegation.js"
cp "$project_root/worker/github_app_connection.js" "$dist_root/server/github_app_connection.js"
cp "$project_root/worker/provider_account_lease.js" "$dist_root/server/provider_account_lease.js"
cp "$project_root/worker/runpod_completion.js" "$dist_root/server/runpod_completion.js"
cp "$project_root/worker/runpod_lifecycle.js" "$dist_root/server/runpod_lifecycle.js"
cp "$project_root/worker/runpod_plan.js" "$dist_root/server/runpod_plan.js"
cp "$project_root/worker/runpod_provider.js" "$dist_root/server/runpod_provider.js"
cp "$project_root/worker/runpod_secret.js" "$dist_root/server/runpod_secret.js"
cp "$project_root/worker/training_authorization.js" "$dist_root/server/training_authorization.js"
cp "$project_root/worker/training_contract.js" "$dist_root/server/training_contract.js"
cp "$project_root/worker/training_plan.js" "$dist_root/server/training_plan.js"
cp "$project_root/worker/training_source.js" "$dist_root/server/training_source.js"
cp "$project_root/.openai/hosting.json" "$dist_root/.openai/hosting.json"
cp "$project_root"/drizzle/*.sql "$dist_root/.openai/drizzle/"

echo "Built $dist_root"
