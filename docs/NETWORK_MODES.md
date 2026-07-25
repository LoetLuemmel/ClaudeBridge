# Networking modes: bridge vs. slirp

*Deutsche Fassung: [NETWORK_MODES.de.md](NETWORK_MODES.de.md)*

The mode is set on the host in `~/.basilisk_ii_prefs` (key `ether`) and read by
Basilisk II **at startup**. It cannot be switched from inside the guest — that
is what `netmode.py` on the host is for.

```bash
python3 netmode.py show      # current mode
python3 netmode.py slirp     # NAT inside the host
python3 netmode.py bridge    # own host on the LAN
```

**Every mode change has two halves.** `netmode.py` only does the host one. The
TCP/IP settings **in the guest** have to follow by hand, or the guest comes back
up with no network at all.

> **ClaudeBridge 2.0 is slirp-only.** The server binds `127.0.0.1` and refuses
> to start on any other address. Bridge mode is documented here because the same
> emulator is also used for AppleBridge — it is not intended for ClaudeBridge.

---

## Mode A — bridge

Host: `ether etherhelper/en8`. The guest is its own host on the WLAN.

TCP/IP control panel in the guest (example values, see
[tcpip-bridge-mode.png](tcpip-bridge-mode.png)):

| Field | Value |
|---|---|
| Connect via | Ethernet |
| Configure | **Manually** |
| IP Address | `192.168.3.244` |
| Subnet mask | `255.255.255.0` |
| Router address | `192.168.3.1` |
| Name server addr. | `192.168.3.1` |
| Search domains | *(empty)* |

The server would then be reachable at `http://<host-lan-ip>:8080/`.

Consequences: the server would have to bind `0.0.0.0`, the **macOS firewall
would have to be off** (a per-app exception does not work, see below), and port
8080 would be open to every device on the WLAN. Avoiding exactly that trade is
the point of ClaudeBridge 2.0.

---

## Mode B — slirp (default)

Host: `ether slirp`. The guest sits behind a NAT *inside* the Mac and no longer
has a LAN address of its own.

TCP/IP control panel in the guest:

| Field | Value |
|---|---|
| Connect via | Ethernet |
| Configure | **Using DHCP Server** |

slirp brings its own DHCP server and hands out:

| Role | Address |
|---|---|
| Guest | `10.0.2.15` |
| Gateway / host | `10.0.2.2` |
| DNS | `10.0.2.3` |

The server is reachable at `http://10.0.2.2:8080/`.

The server binds `127.0.0.1`, the **firewall stays on**, and the attack surface
shrinks from "anyone on the WLAN" to "processes on this machine".

**Verified 2026-07-25:** requests from the guest arrive at the server as
`127.0.0.1` — slirp translates them onto a local socket of the emulator process.
That is why loopback is sufficient, and why the loopback restriction on the
setup page works from the guest.

**The price:** no AppleTalk to other machines, and no inbound connections to the
Classic Mac from outside.

---

## Going back

```bash
python3 netmode.py bridge
```

This restores the `ether` line exactly (the previous value is kept in
`~/.basilisk_ii_prefs.netmode`). Afterwards set the guest's TCP/IP back to
**Manually** with the values from mode A. `netmode.py` writes a backup
`~/.basilisk_ii_prefs.bak-<timestamp>` before every change.

---

## Pitfall: the firewall in bridge mode

In bridge mode a per-app firewall exception is **not** enough. What lands in the
ALF allowlist is `…/Versions/3.12/bin/python3`, while the running process is
`…/Versions/3.12/Resources/Python.app/Contents/MacOS/Python`. The exception
never applies.

The symptom is a **broken pipe** or "Empty reply from server" — *not* connection
refused. ALF lets the TCP handshake complete and terminates the connection
afterwards. The distinguishing detail is that loopback is exempt from ALF while
the LAN is not:

| Target | Result | Log entry |
|---|---|---|
| `127.0.0.1:8080` | HTTP 200 | yes |
| LAN IP `:8080` | `http_code=000` | **no** |

Careful: `nc -z` still reports "succeeded", because it sends no data. Always
test with `curl` or a raw `GET / HTTP/1.0`.
