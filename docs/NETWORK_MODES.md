# Netzwerkmodi: bridge vs. slirp

Der Modus wird host-seitig in `~/.basilisk_ii_prefs` gesetzt (Schlüssel `ether`)
und von Basilisk II **beim Start** gelesen. Er lässt sich nicht aus dem Gast
heraus umschalten — dafür gibt es `netmode.py` auf dem Host.

```bash
uv run python netmode.py show      # aktueller Modus
uv run python netmode.py slirp     # NAT im Host
uv run python netmode.py bridge    # eigener Host im LAN
```

**Jeder Moduswechsel hat zwei Hälften.** `netmode.py` erledigt nur die
host-seitige. Die TCP/IP-Einstellungen **im Gast** müssen von Hand mitgezogen
werden, sonst steht der Gast nach dem Wechsel ohne Netz da.

---

## Modus A — bridge (Ausgangszustand)

Host: `ether etherhelper/en8`, Gast ist ein eigener Host im WLAN.

TCP/IP-Kontrollfeld im Gast (Stand 2026-07-25, siehe
[tcpip-bridge-mode.png](tcpip-bridge-mode.png)):

| Feld | Wert |
|---|---|
| Connect via | Ethernet |
| Configure | **Manually** |
| IP Address | `192.168.3.244` |
| Subnet mask | `255.255.255.0` |
| Router address | `192.168.3.1` |
| Name server addr. | `192.168.3.1` |
| Search domains | *(leer)* |

Bridge-Server erreichbar unter `http://192.168.3.154:8080/`.

Konsequenzen: Server muss auf `0.0.0.0` binden, **macOS-Firewall muss aus**
(Per-App-Freigabe greift nicht, siehe unten), und Port 8080 ist damit für jedes
Gerät im WLAN offen.

---

## Modus B — slirp (NAT im Host)

Host: `ether slirp`. Der Gast sitzt hinter einem NAT *innerhalb* des Macs und
hat keine eigene LAN-Adresse mehr.

TCP/IP-Kontrollfeld im Gast:

| Feld | Wert |
|---|---|
| Connect via | Ethernet |
| Configure | **Using DHCP Server** |

slirp bringt einen eigenen DHCP-Server mit und vergibt:

| Rolle | Adresse |
|---|---|
| Gast | `10.0.2.15` |
| Gateway / Host | `10.0.2.2` |
| DNS | `10.0.2.3` |

Bridge-Server dann erreichbar unter `http://10.0.2.2:8080/`.

Ziel dieses Modus: Server bindet auf `127.0.0.1`, die **Firewall bleibt an**,
und die Angriffsfläche schrumpft von „jeder im WLAN" auf „Prozesse auf diesem
Mac". Ob slirps `10.0.2.2` tatsächlich auf den Host-Loopback abbildet, ist der
Punkt, der gemessen werden muss.

**Preis:** Kein AppleTalk zu anderen Rechnern, keine eingehenden Verbindungen
zum Classic Mac von außen.

---

## Rückweg

```bash
uv run python netmode.py bridge
```

Stellt die `ether`-Zeile exakt wieder her (der vorherige Wert liegt in
`~/.basilisk_ii_prefs.netmode`). Anschließend im Gast TCP/IP zurück auf
**Manually** mit den Werten aus Modus A. `netmode.py` legt vor jeder Änderung
ein Backup `~/.basilisk_ii_prefs.bak-<zeitstempel>` an.

---

## Fallstrick: Firewall im bridge-Modus

Im bridge-Modus reicht eine Per-App-Freigabe der Firewall **nicht**. In der
ALF-Allowlist landet `…/Versions/3.12/bin/python3`, der laufende Prozess ist
aber `…/Versions/3.12/Resources/Python.app/Contents/MacOS/Python`. Die Freigabe
greift nie.

Symptom ist ein **Broken Pipe** bzw. „Empty reply from server", *kein*
Connection Refused: ALF lässt den TCP-Handshake durch und beendet die Verbindung
erst danach. Diagnose-Merkmal — Loopback ist ALF-exempt, das LAN nicht:

| Ziel | Ergebnis | Log-Eintrag |
|---|---|---|
| `127.0.0.1:8080` | HTTP 200 | ja |
| LAN-IP `:8080` | `http_code=000` | **nein** |

Vorsicht: `nc -z` meldet trotzdem „succeeded", weil es keine Daten sendet.
Immer mit `curl` oder einem rohen `GET / HTTP/1.0` testen.
