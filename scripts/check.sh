#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
for script in scripts/*.sh; do bash -n "$script"; done
sh -n scripts/update_config.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
actionlint -shellcheck= -pyflakes=
