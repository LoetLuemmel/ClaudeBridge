#!/bin/bash
# start_bridge.sh - Claude Bridge mit automatischer Firewall-Verwaltung
# Verwendung: sudo ./start_bridge.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
SHARED="/Users/pitforster/Desktop/Share"
HOST="192.168.3.154"
PORT=8080

echo "=== Claude Bridge Starter ==="

# Firewall oeffnen
echo "Firewall wird deaktiviert..."
/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off

echo "Starte Claude Bridge Server..."
echo "Oeffne in Netscape: http://${HOST}:${PORT}/"
echo "Beende mit Ctrl+C"
echo ""

# Server starten (als normaler User, nicht als root)
sudo -u "$SUDO_USER" "$PYTHON" "$SCRIPT_DIR/claude_bridge.py" \
    --host "$HOST" \
    --shared-folder "$SHARED" \
    --port "$PORT"

# Firewall wieder aktivieren wenn Server beendet wird
echo ""
echo "Firewall wird wieder aktiviert..."
/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
echo "Firewall ist wieder aktiv. Fertig."

