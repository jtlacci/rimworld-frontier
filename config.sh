#!/bin/bash
# Frontier configuration — sets paths used by the playtest scripts.
#
# Usage: source "$(dirname "$0")/../config.sh"  (from agents/ or frontier/)
#
# Sets:
#   FRONTIER_DIR  — root of this repo

# Resolve FRONTIER_DIR from wherever this file lives
FRONTIER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FRONTIER_DIR

if [[ ! -d "$FRONTIER_DIR/sdk" ]]; then
    echo "ERROR: sdk/ directory missing under $FRONTIER_DIR" >&2
    return 1 2>/dev/null || exit 1
fi

# Pick a Python with a working stdlib (some Homebrew 3.14 builds have a broken pyexpat).
# Set PYTHON env var if you want to force a specific interpreter.
if [[ -z "${PYTHON:-}" ]]; then
    for candidate in python3 python3.13 python3.12 python3.11 /usr/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1 && \
           "$candidate" -c "from xml.etree import ElementTree as ET; ET.fromstring('<a/>')" >/dev/null 2>&1; then
            PYTHON="$candidate"
            break
        fi
    done
    PYTHON="${PYTHON:-python3}"
fi
export PYTHON

# Prepend the local .bin shim dir so plain `python3` invocations resolve to a
# working interpreter (the prompts and skills hardcode `python3`).
if [[ -x "$FRONTIER_DIR/.bin/python3" ]]; then
    export PATH="$FRONTIER_DIR/.bin:$PATH"
fi
