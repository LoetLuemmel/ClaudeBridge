# ClaudeBridge 2.0

Claude for **Netscape Navigator 3** on **Classic Mac OS**.

An HTTP server that runs on a modern Mac and makes Claude reachable from a
browser built in 1996. No porting, no emulation trick — the server simply
speaks the language of the older shore: HTML 3.2, ISO-8859-1, `META REFRESH`
instead of AJAX.

The vintage machine needs **nothing installed**. It is a pure client.

```
Netscape 3 (System 7.6.1)  ──HTTP/1.0──▶  ClaudeBridge  ──HTTPS──▶  Claude API
        in Basilisk II                     on the host   ──HTTPS──▶  the modern web
```

---

## Quick start

```bash
# with git:
git clone https://github.com/LoetLuemmel/ClaudeBridge.git && cd ClaudeBridge

# without git — macOS does not ship it by default:
curl -L -o cb.zip https://github.com/LoetLuemmel/ClaudeBridge/archive/refs/heads/main.zip
unzip -q cb.zip && cd ClaudeBridge-main

python3 -m pip install -r requirements.txt   # or: uv pip install -r requirements.txt

mkdir -p ~/.config/anthropic
pbpaste > ~/.config/anthropic/api_key     # key on the clipboard, never on screen
chmod 600 ~/.config/anthropic/api_key

./start_bridge.sh                      # or: python3 claude_bridge.py
```

Then, in Netscape on the emulated Mac: **`http://10.0.2.2:8080/`**

On the host itself: `http://127.0.0.1:8080/`

> **Every command runs inside that directory** — `start_bridge.sh`,
> `netmode.py`, the tests. A new terminal window starts in your home directory
> instead. `pwd` settles it.
>
> **Updating:** with a checkout, `git pull`. From a ZIP there is no repository,
> so `git pull` answers `fatal: not a git repository` — download the archive
> again instead. Either way your API key is untouched: it lives in
> `~/.config/anthropic/`, not in this directory.
>
> Naming the virtual environment `.venv` inside the checkout avoids a confusing
> case: if it carries the same name as the directory, the prompt shows that word
> twice for two unrelated reasons. `start_bridge.sh` also finds `.venv`
> automatically.

---

## Requirements

> **Use `python3 -m pip`, not a bare `pip`.** Current macOS ships no standalone
> `pip` command, and a virtual environment created by `uv venv` does not contain
> one either — so `pip install` fails with `command not found` even with an
> environment active. The module form always works.

**Host** — macOS with Python 3.8+, and three libraries:

| Package | Used for |
|---|---|
| `PyYAML` | reading `config.yaml` |
| `beautifulsoup4` | simplifying modern HTML down to 3.2 |
| `Pillow` | converting images to GIF for Netscape |

Everything else is standard library. There is no framework and no Anthropic SDK
— the API call goes through `urllib`.

**Guest** — Mac OS 7.5 or 7.6.1 with Netscape Navigator 3.04. Two settings, no
installation:

- **TCP/IP** control panel → Connect via `Ethernet`, Configure `Using DHCP Server`
- **Netscape** → character set `Western` (ISO-8859-1)

**Emulator** — Basilisk II in **slirp** mode (`ether slirp` in
`~/.basilisk_ii_prefs`). See *Networking* below.

---

## What it does

The home page offers seven tools, each its own endpoint:

| | Tool | |
|---|---|---|
| `[*]` | **Claude Chat** | open conversation, context across rounds |
| `[C]` | **Code Assistant** | specialised in THINK C 7.0 for Classic Mac |
| `[R]` | **Resource Generator** | Rez source for `MENU`, `DLOG`, `DITL`, `WIND`, `ICON` |
| `[?]` | **Ask & Answer** | general Toolbox questions |
| `[W]` | **Web Proxy** | modern HTTPS sites, simplified to HTML 3.2 |
| `[F]` | **Shared Folder** | browse the emulator's shared folder, send files to Claude |
| `[V]` | **History** | past questions and answers, persistent across restarts |

Plus `/setup` for host configuration — served to loopback clients only.

### Why it looks like 1996

Netscape 3 understands HTML 3.2. No CSS, no JavaScript, no modern form
elements. Every design decision follows from that:

| Modern web | ClaudeBridge |
|---|---|
| CSS layout | `<TABLE>` with `BGCOLOR` |
| AJAX / fetch | `<META HTTP-EQUIV="Refresh">` |
| UTF-8 | ISO-8859-1 |
| WebSockets | polling every three seconds |

A request creates a job, starts a background thread and returns a waiting page
immediately. That page refreshes onto `/result/<id>` every three seconds until
the answer is ready — the only form of "asynchronous" this browser knows.

### The web proxy

Netscape 3 speaks SSL 2.0/3.0 with 40-bit export ciphers, which the modern web
no longer accepts. The proxy fetches over HTTPS, strips scripts, styles,
`<div>` and `<span>`, and serves plain HTTP. Images are scaled to 500 px,
reduced to an adaptive 24–64 colour palette and delivered as GIF.

Requests to loopback, private ranges, link-local, multicast and reserved
addresses are refused, including through redirects — otherwise the proxy would
be an open relay for anyone who can reach the port.

---

## Networking

**ClaudeBridge 2.0 is slirp-only.** The server binds `127.0.0.1` and refuses to
start on any other address.

In slirp mode the guest sits behind a NAT inside the host and reaches it at
`10.0.2.2`, which arrives on the loopback interface. The macOS firewall can
stay on and the port is never exposed to the LAN.

Bridge mode — where the guest is its own host on the network — would require
binding `0.0.0.0` **and** switching the firewall off entirely. Avoiding that
trade is the point of this version.

`netmode.py` switches the emulator's mode and backs up the prefs first:

```bash
python3 netmode.py show      # current mode
python3 netmode.py slirp     # NAT inside the host
python3 netmode.py bridge    # own host on the LAN (not for this version)
```

A mode change has two halves — this only does the host one. The guest's TCP/IP
control panel has to follow. See [`docs/NETWORK_MODES.md`](docs/NETWORK_MODES.md).

---

## Configuration

`config.yaml`, or `/setup` in the browser:

| Setting | Default | |
|---|---|---|
| `server.host` | `127.0.0.1` | **fixed**, see Networking |
| `server.port` | `8080` | |
| `claude.model` | `claude-opus-4-5-20251101` | |
| `claude.max_tokens` | `4096` | |
| `jobs.refresh_interval` | `3` | seconds; below 2 overwhelms Netscape 3 |
| `files.shared_folder` | `~/Desktop/Share` | `null` disables the feature |
| `proxy.block_private_networks` | `true` | the SSRF filter |
| `setup.require_loopback` | `true` | who may reach `/setup` |

The API key is **not** in `config.yaml` — that file is version-controlled. It is
read from `ANTHROPIC_API_KEY`, then `~/.config/anthropic/api_key`, then `.env`.

Write it with `pbpaste`, not with `echo 'sk-ant-…' > file`. The `echo` form puts
the key on screen, into the scrollback and into `~/.zsh_history`, where it
stays.

---

## Encoding

Three separate concerns that fail in three different ways. Every one of them
cost real debugging time:

| Layer | Direction | Correct answer |
|---|---|---|
| Page output | server → browser | ISO-8859-1 |
| HTML escaping | server → browser | decimal references only — `html.escape()` emits `&#x27;`, which Netscape 3 renders literally |
| Form input | browser → server | ISO-8859-1 in `parse_qs` — a browser submits in the *document's* charset, not in MacRoman |

Do not change any of these without testing on a real Classic Mac.

---

## Tests

```bash
python3 test_claude_bridge.py     # 41 tests, unittest, no network needed
```

Covers path traversal, sanitizing, Netscape-safe escaping, the SSRF filter
(including the redirect bypass) and the slirp-only bind rule.

---

## Wanted: someone to finish the native client

`ClassicClient/` holds a THINK C 7.0 application — event loop, MacTCP
networking, preferences, menus, Rez resources, about 2,900 lines. It would talk
to the server over the JSON responses returned when the `User-Agent` contains
`ClaudeAssistant`, skipping the browser entirely.

**It has never been compiled, and as written it will not work.** Three known
problems, all in `network.c`:

| | |
|---|---|
| `URLEncode()` | percent-encodes raw MacRoman bytes, but the server decodes ISO-8859-1 — so `ü` (`0x9F`) arrives as something else entirely |
| chat request | sends the field `prompt`, while `/chat` expects `message` |
| `URLEncode()` | writes into a fixed buffer with no length check — on a 68k without memory protection that takes the whole machine down |

The server side is finished and verified: the JSON branch answers correctly,
umlauts included, and can be exercised with plain `curl` — no vintage hardware
required.

```bash
curl -H "User-Agent: ClaudeAssistant/1.0" \
     -X POST --data 'message=Hallo' http://127.0.0.1:8080/chat
# {"job_id": "1"}
```

What is missing is a working client. If you have THINK C 7.0 and an afternoon,
this is a well-defined piece of work with a known finish line. Everything else
in this repository works through the browser alone in the meantime.

---

## License

MIT — see [LICENSE](LICENSE).
