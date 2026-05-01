#!/bin/bash
# Frontier configuration — sources paths and model assignments.
#
# Usage: source "$(dirname "$0")/../config.sh"  (from agents/ or frontier/)
#
# Sets:
#   FRONTIER_DIR  — root of this repo (the unified harness + agent + SDK)

# Resolve FRONTIER_DIR from wherever this file lives
FRONTIER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FRONTIER_DIR

if [[ ! -d "$FRONTIER_DIR/sdk" ]]; then
    echo "ERROR: sdk/ directory missing under $FRONTIER_DIR" >&2
    return 1 2>/dev/null || exit 1
fi

# Qwen API config
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope-us.aliyuncs.com/compatible-mode/v1}"
# DASHSCOPE_API_KEY must be set in environment

# Model assignments
export MODEL_OVERSEER="${MODEL_OVERSEER:-qwen3.5-397b-a17b}"
export MODEL_REPORTER="${MODEL_REPORTER:-qwen3.5-397b-a17b}"

# Agent harness
AGENT_HARNESS="$FRONTIER_DIR/frontier/agent_harness.py"
export AGENT_HARNESS
