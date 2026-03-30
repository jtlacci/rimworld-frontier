#!/bin/bash
# Frontier configuration — sources paths for both repos.
#
# Usage: source "$(dirname "$0")/../config.sh"  (from agents/)
#        source "$(dirname "$0")/../config.sh"  (from frontier/)
#
# Sets:
#   FRONTIER_DIR  — root of this repo (rimworld-frontier)
#   AGENT_REPO    — root of the agent repo (rimworld-tcp / rimworld-agent)

# Resolve FRONTIER_DIR from wherever this file lives
FRONTIER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FRONTIER_DIR

# AGENT_REPO can be overridden via env var; defaults to sibling directory
AGENT_REPO="${AGENT_REPO:-$(cd "$FRONTIER_DIR/../rimworld-tcp" 2>/dev/null && pwd)}"
export AGENT_REPO

if [[ ! -d "$AGENT_REPO/sdk" ]]; then
    echo "ERROR: AGENT_REPO not found or missing sdk/ directory: $AGENT_REPO" >&2
    echo "Set AGENT_REPO env var to point to the rimworld-agent checkout." >&2
    exit 1
fi

# Qwen API config
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope-us.aliyuncs.com/compatible-mode/v1}"
# DASHSCOPE_API_KEY must be set in environment

# Model assignments
export MODEL_OVERSEER="${MODEL_OVERSEER:-qwen-plus-us}"
export MODEL_AUDITOR="${MODEL_AUDITOR:-qwen3.5-plus}"
export MODEL_TRAINER="${MODEL_TRAINER:-qwen3.5-plus}"
export MODEL_CHALLENGER="${MODEL_CHALLENGER:-qwen-plus-us}"

# Agent harness
AGENT_HARNESS="$FRONTIER_DIR/frontier/agent_harness.py"
export AGENT_HARNESS
