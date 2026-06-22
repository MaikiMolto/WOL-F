<div align="center">
  <img src="app/templates/images/wol-f/logo.png" width="160" alt="WOL-F" />

  # WOL-F · Wake-On-LAN Fleet

  **A modern, security-hardened Wake/Sleep-on-LAN fleet manager — wake and shut down the computers on your LAN from a clean web GUI.**

  _by **MaikiMolto & Nex** · inspired by [GPTWOL](https://github.com/Misterbabou/gptwol)_
</div>

---

WOL-F is a lightweight, self-hosted web app to **wake up** (Wake-on-LAN) and **shut down** (Sleep-on-LAN) the computers on your LAN — with per-device scheduling, live status checks, an ARP network scanner, optional login, optional built-in HTTPS, and a polished dark/light, DE/EN interface.

> **Inspired by [GPTWOL](https://github.com/Misterbabou/gptwol)** (MIT © Misterbabou). WOL-F is a heavily reworked fork: redesigned UI, full DE/EN i18n, security hardening (CSRF tokens, security headers, login rate-limiting, persistent secret key), optional built-in HTTPS, mobile fixes and more.

## Features

- 🔌 **Wake-on-LAN** — send magic packets to wake computers
- 😴 **Sleep-on-LAN** — shut computers down (via [SR-G/sleep-on-lan](https://github.com/SR-G/sleep-on-lan))
- ⏰ **Scheduling** — per-device wake/sleep cron schedules via a beginner-friendly builder (presets, weekdays, time)
- 📡 **Status checks** — ICMP ping, ARP or TCP port (configurable timeouts)
- 🔍 **ARP network scan** to discover & add devices
- ➕ **Add / edit / delete** devices (toggleable)
- 🔎 **Search** by name, MAC or IP · **Sort** by name / IP / MAC
- 🌗 **Dark & light mode** · 🌍 **DE / EN** with live switching
- 🔐 **Optional login** (single user) — CSRF-protected, rate-limited, hardened session cookie
- 🔒 **Optional built-in HTTPS** — self-signed cert auto-generated, no reverse proxy required
- 📱 Responsive (desktop + mobile), low footprint (~20 MB RAM)

## Screenshots

_See [`docs/screenshots/`](docs/screenshots) — polished dark/light desktop UI, mobile view and login._

## Quick start (Docker)

> [!CAUTION]
> - The container must run in **host network mode** to send WOL packets on your LAN.
> - Make sure the chosen `PORT` is free on your host.
> - Make sure BIOS/OS is configured to allow Wake-on-LAN.
> - Don't expose WOL-F to the internet without protection — enable login + HTTPS, or put it behind a reverse proxy.

### docker compose (recommended)

```yaml
services:
  wol-f:
    container_name: wol-f
    image: maikimolto/wol-f:latest
    network_mode: host
    restart: unless-stopped
    environment:
      - TZ=Europe/Berlin
      #- PORT=5000              # Web UI port; default 5000
      #- IP=0.0.0.0             # listen address
      #- LANGUAGE=de            # de | en ; default de
      #- ENABLE_LOGIN=false     # single-user login
      #- USERNAME=admin
      #- PASSWORD=              # REQUIRED when ENABLE_LOGIN=true (no default)
      #- SECRET_KEY=            # Flask secret; auto-persisted in /app/db if unset
      #- ENABLE_HTTPS=false     # serve HTTPS directly (self-signed, no proxy needed)
      #- SSL_CERT=/app/db/wol-f-cert.pem
      #- SSL_KEY=/app/db/wol-f-key.pem
      #- SESSION_COOKIE_SECURE=false   # auto-on when ENABLE_HTTPS=true
      #- ENABLE_ADD_DEL=true
      #- ENABLE_REFRESH=true
      #- REFRESH_INTERVAL=30
      #- PING_TIMEOUT=300
      #- ARP_INTERFACE=eth0
      #- ARP_TIMEOUT=300
      #- TCP_TIMEOUT=1
      #- ENABLE_L2_WOL_PACKET=false
      #- L2_INTERFACE=eth0
      #- SCRIPT_NAME=/my-app    # run under a subpath
      #- LOG_LEVEL=INFO
      #- GUNICORN_WORKERS=3
      #- GUNICORN_THREADS=2
      #- GUNICORN_TIMEOUT=60
    volumes:
      - ./appdata/db:/app/db
      - ./appdata/cron:/etc/cron.d
```
```
docker compose up -d
```

### docker run

```
docker run -d --name wol-f --network host --restart unless-stopped \
  -e TZ=Europe/Berlin -e PORT=5000 \
  -v ./appdata/db:/app/db -v ./appdata/cron:/etc/cron.d \
  maikimolto/wol-f:latest
```

### Build from source

```
git clone https://github.com/MaikiMolto/wol-f.git && cd wol-f
docker build -t wol-f:latest .
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `TZ` | `UTC` | Timezone (used for cron) |
| `PORT` | `5000` | Web UI port |
| `IP` | `0.0.0.0` | Listen address (IPv4/IPv6) |
| `LANGUAGE` | `de` | UI default language (`de` / `en`) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARN` / `ERROR` |
| `ENABLE_LOGIN` | `false` | Enable single-user login |
| `USERNAME` | `admin` | Login username |
| `PASSWORD` | — | **Required when `ENABLE_LOGIN=true`** (app refuses to start without it) |
| `SECRET_KEY` | _auto_ | Flask secret for sessions/CSRF; auto-persisted in `/app/db` if unset |
| `ENABLE_HTTPS` | `false` | Serve HTTPS directly with a self-signed cert (no reverse proxy needed) |
| `SSL_CERT` / `SSL_KEY` | `/app/db/wol-f-*.pem` | Custom TLS cert/key (used with `ENABLE_HTTPS`; auto-generated if missing) |
| `SESSION_COOKIE_SECURE` | `false` | Send session cookie only over HTTPS (auto-on with `ENABLE_HTTPS`) |
| `ENABLE_ADD_DEL` | `true` | Show add/delete buttons |
| `ENABLE_REFRESH` | `true` | Auto status refresh |
| `REFRESH_INTERVAL` | `30` | Status check interval (s) |
| `PING_TIMEOUT` | `300` | Ping timeout (ms) |
| `ARP_INTERFACE` | — | ARP interface for scan/test |
| `ARP_TIMEOUT` | `300` | ARP timeout (ms) |
| `TCP_TIMEOUT` | `1` | TCP check timeout (s) |
| `ENABLE_L2_WOL_PACKET` | `false` | Use an L2 WOL packet instead of L4 |
| `L2_INTERFACE` | `eth0` | Interface for L2 WOL |
| `SCRIPT_NAME` | — | Run the app under a subpath |
| `GUNICORN_WORKERS` | `3` | Number of gunicorn workers |
| `GUNICORN_THREADS` | `2` | Threads per worker |
| `GUNICORN_TIMEOUT` | `60` | Worker timeout (s) |

## Access & HTTPS

By default WOL-F serves plain **HTTP** on `PORT`. Three ways to reach it:

- **Direct HTTP** — `http://<host>:<PORT>` works out of the box (browsing, add/edit/delete all work).
- **Reverse proxy (recommended for HTTPS)** — put Zoraxy/Caddy/nginx/Traefik in front and let it terminate TLS; the app speaks HTTP to the proxy.
- **Built-in HTTPS (no proxy)** — set `ENABLE_HTTPS=true`. The app then serves HTTPS directly on `PORT` using a self-signed certificate auto-generated in `/app/db` (the browser shows a one-time warning). Provide your own `SSL_CERT`/`SSL_KEY` to avoid the warning.

## Configure Sleep-on-LAN

WOL-F shuts a computer down by sending a **reverse-MAC** WOL magic packet on **UDP port 9**, which [SR-G/sleep-on-lan](https://github.com/SR-G/sleep-on-lan) listens for (no API configuration required).

**Linux (`sol.json`):**
```json
{
  "Listeners": ["UDP:9"],
  "LogLevel": "INFO",
  "Commands": [{ "Operation": "shutdown", "Command": "poweroff", "Default": true }]
}
```

**Windows (`sol.json`):**
```json
{
  "Listeners": ["UDP:9"],
  "LogLevel": "INFO",
  "Commands": [{ "Operation": "shutdown", "Command": "shutdown /s /t 0 /f", "Default": true }]
}
```
Then add an inbound Windows Defender Firewall rule allowing UDP port 9.

## FAQ

<details>
<summary>Is there a GUI calendar for the automatic wake/shutdown schedules?</summary>
<br>
Schedules use cron syntax behind a beginner-friendly builder (presets, weekdays, time). To keep WOL-F simple there is no full calendar UI. See <a href="https://crontab.guru/">crontab.guru</a> if you want to craft a custom expression.
</details>

## Credits

- **WOL-F** — by **MaikiMolto & Nex**
- Inspired by **[GPTWOL](https://github.com/Misterbabou/gptwol)** by Misterbabou (MIT)
- Sleep-on-LAN powered by **[SR-G/sleep-on-lan](https://github.com/SR-G/sleep-on-lan)**

## License

MIT — see [LICENSE.md](LICENSE.md). Original GPTWOL work © Misterbabou; WOL-F modifications © MaikiMolto & Nex.
