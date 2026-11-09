#!/usr/bin/env bash
# Fixed, argument-free root operation. Never interpolate user input.
set -euo pipefail
if [[ "${#}" -ne 0 ]]; then exit 2; fi
systemctl list-units --state=failed --all --no-legend --plain --no-pager --type=service | awk 'END { print NR+0 }'
