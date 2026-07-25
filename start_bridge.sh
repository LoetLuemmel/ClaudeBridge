#!/bin/bash
# start_bridge.sh - Start ClaudeBridge 2.0
#
# ClaudeBridge 2.0 is slirp-only. The emulator sits behind a NAT inside this
# host and reaches the server at 10.0.2.2:8080, which arrives on loopback -
# so the server binds 127.0.0.1 and the macOS firewall STAYS ON.
#
# The previous version of this script did the opposite: it bound a LAN address
# and ran `socketfilterfw --setglobalstate off`, because back then the emulator
# was bridged onto the WLAN and the firewall blocked the port. That trade is
# exactly what this version exists to avoid, so none of it happens any more.
# For a guest that has to be reachable on the LAN, use AppleBridge.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -x .venv/bin/python ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "=== ClaudeBridge 2.0 ==="

# Warn if the emulator is not in slirp mode - the server would start fine but
# the guest would have no route to it.
PREFS="$HOME/.basilisk_ii_prefs"
if [ -f "$PREFS" ]; then
    MODE=$(grep '^ether ' "$PREFS" | head -1 | cut -d' ' -f2-)
    if [ "$MODE" != "slirp" ]; then
        echo
        echo "WARNING: Basilisk II is set to '$MODE', not slirp."
        echo "         The server will start, but the guest will not reach it."
        echo "         Switch with:  $PYTHON netmode.py slirp"
        echo
    fi
fi

echo "Guest URL: http://10.0.2.2:8080/"
echo "Host URL : http://127.0.0.1:8080/"
echo "Stop with Ctrl+C"
echo

exec "$PYTHON" claude_bridge.py
