#!/usr/bin/env bash
set -euo pipefail

uv sync --locked --dev
uv run --locked --group dev anima-validate

OPA_IMAGE="openpolicyagent/opa:1.20.1@sha256:39daf255ae7f25d81103f03a0c18308a50b7b5bb67907bed6166f70e24a970ff"
if command -v opa >/dev/null 2>&1; then
    opa test policy/phase4 --fail-on-empty
elif command -v docker >/dev/null 2>&1; then
    policy_tmp=$(mktemp -d)
    cp policy/phase4/* "$policy_tmp"/
    chmod 755 "$policy_tmp"
    chmod 644 "$policy_tmp"/*
    docker run --rm -v "$policy_tmp:/policies:ro" "$OPA_IMAGE" test /policies --fail-on-empty
else
    echo "OPA validation requires opa or Docker" >&2
    exit 1
fi
