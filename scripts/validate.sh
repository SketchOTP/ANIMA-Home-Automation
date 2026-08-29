#!/usr/bin/env bash
set -euo pipefail

uv sync --locked --dev
uv run --locked --group dev anima-validate
