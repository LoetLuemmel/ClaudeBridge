#!/usr/bin/env python3
"""
Emulator Network Mode Switch
=============================

Works with Basilisk II and SheepShaver - both share the preferences format and
the 'ether' key. Defaults to ~/.basilisk_ii_prefs; for SheepShaver set
BASILISK_PREFS=~/.sheepshaver_prefs.

Switches the emulator between the two networking modes and, with that, decides
how exposed the Claude Bridge server has to be:

  bridge  ether etherhelper/en8   Guest is its own host on the LAN.
                                  Server must bind 0.0.0.0, firewall must be off,
                                  everyone on the WLAN can reach port 8080.

  slirp   ether slirp             Guest sits behind a NAT inside this Mac
                                  (10.0.2.x). Server can bind loopback, firewall
                                  stays on. Guest loses its own LAN presence -
                                  no AppleTalk to other machines, no inbound
                                  connections to the Classic Mac.

This cannot live in the Classic Mac client: the setting is read by Basilisk II
before the guest boots, and changing it requires restarting the emulator.

Usage:
    uv run python netmode.py show
    uv run python netmode.py slirp
    uv run python netmode.py bridge
    uv run python netmode.py slirp --restart    # also restarts Basilisk II
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PREFS = Path(os.environ.get("BASILISK_PREFS", Path.home() / ".basilisk_ii_prefs"))
# Remembers the exact 'ether' line we replaced, so switching back restores the
# original device instead of guessing 'en8'.
SIDECAR = PREFS.with_name(PREFS.name + ".netmode")

# Where to look for the emulator, in order. Override with BASILISK_APP.
BASILISK_CANDIDATES = [
    "/Applications/BasiliskII.app",
    "~/Applications/BasiliskII.app",
    "~/Documents/Basilisk/BasiliskII.app",
    "~/Documents/BasiliskII/BasiliskII.app",
]

DEFAULT_BRIDGE = "etherhelper/en8"


def find_basilisk():
    """Locate BasiliskII.app, or None if it is not where we look.

    Only needed for --restart; switching the mode itself just edits the prefs.
    """
    override = os.environ.get("BASILISK_APP")
    if override:
        path = Path(override).expanduser()
        return path if path.exists() else None
    for candidate in BASILISK_CANDIDATES:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


def read_prefs():
    if not PREFS.exists():
        sys.exit(f"Prefs nicht gefunden: {PREFS}")
    return PREFS.read_text(encoding="utf-8", errors="replace").splitlines()


def current_ether(lines):
    """Return the value of the 'ether' key, or None if unset."""
    for line in lines:
        if line.startswith("ether "):
            return line[len("ether "):].strip()
    return None


def describe(value):
    if value is None:
        return "nicht gesetzt"
    if value == "slirp":
        return "slirp  (NAT im Host, Gast hat keine eigene LAN-Adresse)"
    if value.startswith("etherhelper/"):
        return f"bridge ({value} - Gast ist eigener Host im LAN)"
    return value


def is_running():
    """True if Basilisk II or SheepShaver is running.

    Both emulators share the preferences format and the 'ether' key, so this
    script works for either - point BASILISK_PREFS at ~/.sheepshaver_prefs.
    """
    for name in ("BasiliskII", "SheepShaver"):
        if subprocess.run(["pgrep", "-f", name], capture_output=True).returncode == 0:
            return True
    return False


def backup():
    """Copy the prefs aside. Never overwrites an existing backup - two switches
    within the same second must not collapse into one file."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = PREFS.parent / f"{PREFS.name}.bak-{stamp}"
    counter = 1
    while dest.exists():
        dest = PREFS.parent / f"{PREFS.name}.bak-{stamp}-{counter}"
        counter += 1
    shutil.copy2(PREFS, dest)
    return dest


def write_ether(lines, value):
    """Replace the 'ether' line, preserving position and every other setting."""
    out, replaced = [], False
    for line in lines:
        if line.startswith("ether ") and not replaced:
            out.append(f"ether {value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"ether {value}")
    PREFS.write_text("\n".join(out) + "\n", encoding="utf-8")


def switch(target, restart):
    lines = read_prefs()
    current = current_ether(lines)

    if target == "slirp":
        new = "slirp"
        # Remember what we are replacing so 'bridge' can restore it exactly
        if current and current != "slirp":
            SIDECAR.write_text(current + "\n", encoding="utf-8")
    else:
        if SIDECAR.exists():
            new = SIDECAR.read_text(encoding="utf-8").strip() or DEFAULT_BRIDGE
        else:
            new = DEFAULT_BRIDGE

    if current == new:
        print(f"Bereits im Modus: {describe(current)}")
        return

    if is_running() and not restart:
        print("HINWEIS: Basilisk II laeuft gerade.")
        print("         Die Aenderung greift erst beim naechsten Start.")
        print("         Mit --restart wird der Emulator neu gestartet")
        print("         (nicht gesicherte Arbeit im Gast geht dabei verloren).")
        print()

    dest = backup()
    write_ether(lines, new)
    print(f"Backup : {dest}")
    print(f"Vorher : {describe(current)}")
    print(f"Nachher: {describe(new)}")

    if restart:
        if is_running():
            print("\nBeende Basilisk II ...")
            subprocess.run(["pkill", "-f", "BasiliskII.app"])
        print("Starte Basilisk II ...")
        app = find_basilisk()
        if app:
            subprocess.run(["open", "-a", str(app)])
        else:
            print("BasiliskII.app nicht gefunden - bitte von Hand starten.")
            print("Suchpfade:", ", ".join(BASILISK_CANDIDATES))
            print("Oder BASILISK_APP=/pfad/zu/BasiliskII.app setzen.")

    print()
    if new == "slirp":
        print("Naechster Schritt: TCP/IP im Gast auf 'Using DHCP Server' stellen.")
        print("Der Gast erreicht den Host dann ueber 10.0.2.2:8080.")
    else:
        print("ACHTUNG: ClaudeBridge 2.0 ist slirp-only und wird im bridge-Modus")
        print("         NICHT mehr erreichbar sein - der Server bindet Loopback")
        print("         und weigert sich, auf 0.0.0.0 zu starten.")
        print()
        print("Der bridge-Modus ist fuer AppleBridge gedacht. Im Gast ausserdem")
        print("TCP/IP zurueck auf 'Manually' mit der festen Adresse stellen.")


def show():
    lines = read_prefs()
    current = current_ether(lines)
    print(f"Prefs        : {PREFS}")
    print(f"Modus        : {describe(current)}")
    print(f"Emulator     : {'laeuft' if is_running() else 'gestoppt'}")
    if SIDECAR.exists():
        print(f"Gemerkt      : {SIDECAR.read_text(encoding='utf-8').strip()} (fuer Rueckschaltung)")


def main():
    p = argparse.ArgumentParser(description="Basilisk II Netzwerkmodus umschalten")
    p.add_argument("mode", choices=["show", "slirp", "bridge"])
    p.add_argument("--restart", action="store_true",
                   help="Basilisk II neu starten (Arbeit im Gast geht verloren)")
    args = p.parse_args()

    if args.mode == "show":
        show()
    else:
        switch(args.mode, args.restart)


if __name__ == "__main__":
    main()
