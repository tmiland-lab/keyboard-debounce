#!/usr/bin/env bash
# Uninstall the kbd-debounce systemd service.
set -euo pipefail

UNIT_NAME="kbd-debounce"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --unit-name) UNIT_NAME="$2"; shift 2 ;;
    -h|--help) echo "Usage: sudo ./uninstall.sh [--unit-name kbd-debounce]"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "run as root: sudo ./uninstall.sh" >&2; exit 1; }

systemctl disable --now "${UNIT_NAME}.service" 2>/dev/null || true
rm -f "/etc/systemd/system/${UNIT_NAME}.service"
systemctl daemon-reload
echo "Removed ${UNIT_NAME}.service."
echo "/usr/local/bin/kbd-debounce.py was left in place — delete it manually if unused."
