#!/usr/bin/env bash
# japan-project-rules init: generate a local project.json for one project (never commits / pushes).
# Usage: ./init.sh <path-to-project> <project-name> [--out <config>] [--answers answers.json]
#        ./init.sh <path-to-project> <project-name> --emit-questions [questions.json]
#        ./init.sh <path-to-project> <project-name> --verify --out <config>
#        ./init.sh - <project-name> --no-scan --answers answers.json --out <config>
# Details: python3 tools/init_project.py --help
set -euo pipefail
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null || { echo "ERROR: python3 is required" >&2; exit 2; }
exec python3 "$KIT_DIR/tools/init_project.py" "$@"
