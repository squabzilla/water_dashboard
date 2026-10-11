#!/usr/bin/env bash

# script I made to run vite, since I'll need to do it a lot lol
# remember to do this in its own terminal!

set -euo pipefail

CURRENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

#cmd="uv run uvicorn backend.backend_main:app --reload --reload-dir backend --reload-dir data_pipeline"
cmd="cd frontend && npm run dev"
eval "$cmd"