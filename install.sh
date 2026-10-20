#!/usr/bin/env bash
# Install kbd-debounce as a systemd system service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_NAME="kbd-debounce"
THRESHOLD=75
NAME=""

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh --name "Keyboard Name" [--threshold 75] [--unit-name kbd-debounce]

  --name NAME       substring of the keyboard's device name
                    (list candidates with: sudo python3 kbd-debounce.py --list)
  --threshold MS    debounce threshold in milliseconds (default: 75)
  --unit-name NAME  systemd unit name (default: kbd-debounce)

Uninstall with: sudo ./uninstall.sh [--unit-name kbd-debounce]
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --threshold) THRESHOLD="$2"; shift 2 ;;
    --unit-name) UNIT_NAME="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown option: $1" >&2; usage ;;
  esac
done

[[ -n "$NAME" ]] || usage
[[ $EUID -eq 0 ]] || { echo "run as root: sudo ./install.sh ..." >&2; exit 1; }

install -m 0755 "$SCRIPT_DIR/kbd-debounce.py" /usr/local/bin/kbd-debounce.py

cat > "/etc/systemd/system/${UNIT_NAME}.service" <<EOF
[Unit]
Description=Keyboard debounce filter for ${NAME} (key chatter / double-typing fix)
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/kbd-debounce.py --name "${NAME}" --threshold ${THRESHOLD}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}.service"
systemctl --no-pager --lines=5 status "${UNIT_NAME}.service" || true
echo
echo "Installed. Watch for caught bounces with:"
echo "  journalctl -u ${UNIT_NAME}.service -f"
