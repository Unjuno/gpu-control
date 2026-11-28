#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 3 && $# != 4 ]]; then
    echo "Usage: $0 MAP_CHECKOUT REVIEWED_SHA PYTHON_3_11_IMAGE_AT_DIGEST [NEW_MODAL_CONTEXT_DIR]" >&2
    exit 2
fi
checkout=$1
sha=$2
base=$3
if [[ ! $sha =~ ^[0-9a-f]{40}$ || ! $base =~ ^(docker\.io/library/)?python@sha256:[0-9a-f]{64}$ ]]; then
    echo "Expected a full commit SHA and a digest-pinned Python base." >&2
    exit 2
fi
git -C "$checkout" cat-file -e "$sha^{commit}"
if [[ $# == 4 ]]; then
    context=$4
    mkdir -- "$context"
else
    context=$(mktemp -d)
    trap 'rm -rf "$context"' EXIT
fi
mkdir "$context/source"
git -C "$checkout" archive "$sha" -- src/model_as_a_paper configs/map44.json |
    tar -xf - -C "$context/source"
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ $# == 4 ]]; then
    sed -e '/^ARG PYTHON_BASE$/d' \
        -e 's|^FROM .*|FROM '"$base"'|' \
        -e 's|^ARG MAP_SOURCE_SHA$|ARG MAP_SOURCE_SHA='"$sha"'|' \
        "$script_dir/Dockerfile" > "$context/Dockerfile"
    exit 0
fi
docker build --platform linux/amd64 --file "$script_dir/Dockerfile" \
    --build-arg "PYTHON_BASE=$base" --build-arg "MAP_SOURCE_SHA=$sha" \
    --tag "ghcr.io/unjuno/gpu-control-map-training:$sha" "$context"
