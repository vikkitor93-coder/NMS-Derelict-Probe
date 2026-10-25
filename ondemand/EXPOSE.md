# Exposing the on-demand map server (plan only, NOT done)

Nothing in this folder exposes anything. `ondemand_server.py` binds to **127.0.0.1:8791 only** (hard-coded, there is no
option to bind elsewhere). To let visitors reach it, a tunnel running on the same PC forwards public HTTPS requests to
that local port. This file compares the three ways to do that. The user decides; none of the commands below has been run.

What a visitor can reach once a tunnel points at port 8791: `GET /api/map/<ADDRESS16>` and `GET /api/health`, nothing
else (all other paths 404, POST/PUT 405, request bodies refused). No scanner, no viewer, no files, no game assets.
The server limits abuse itself (queue cap 20, 10 new maps/min and 120 requests/min per client, 90 s waits, 64 connections).

## Summary

| | (a) Tailscale Funnel | (b) Cloudflare named tunnel | (c) Cloudflare quick tunnel |
|---|---|---|---|
| Cost | free (already installed, v1.104.2) | domain on Cloudflare, about $10/year; tunnel free | free |
| Stable URL | yes (`<machine>.<tailnet>.ts.net`) | yes (your domain) | **no, new random URL at every start** |
| Home IP hidden | yes | yes | yes |
| Caches repeat requests at the edge | no (every request reaches the PC) | yes, with one free Cache Rule | no |
| DDoS / WAF / extra rate limit in front | no | yes (free tier: DDoS, 1 rate-limit rule, bot fight mode) | basic only |
| Needs a domain | no | yes | no |
| Fit | start now, zero cost | best long-term | demos only |

**Recommendation:** go live with (a) Funnel first (free, installed, three commands, reversible with one command). Rename
the machine to a neutral name before the first start (see below). Move to (b) later if traffic grows or you want edge
caching: the site only holds one URL value, so switching costs one config change. Do not use (c) for the real site.

## How the site learns the URL (all three)

One config value in the site config: `viewer/static/config.js`, key `DV_CONFIG.ondemandBase` (to be added with the viewer
button; empty means "no map server": the button is hidden). Example: `"ondemandBase": "https://HOST.TAILNET.ts.net"`.
The site calls `ondemandBase + "/api/map/<ADDRESS16>"`. Changing it needs a re-publish of the site (the Pages deploy).
That is why (c) is a poor fit: its URL changes on every restart, so the site would have to be re-published each time.

## (a) Tailscale Funnel

- **Home IP hidden?** Yes. The `*.ts.net` name resolves to Tailscale's Funnel ingress servers, not to your router. Visitors
  connect to those servers over TLS, and Tailscale relays the request to your PC over its WireGuard tunnel (your PC dials
  out; no port forwarding, no open inbound port). Tailscale itself and your other tailnet devices know your IP; visitors do not.
- **Hostname.** Shown as `HOST.TAILNET.ts.net` today (`tailscale status` shows machine `HOSTNAME`).
  - The machine part can be changed: `tailscale set --hostname=nms-atlas` (checked with `tailscale set --help`: the flag
    exists in 1.104.2), or Admin console > Machines > the device > Edit machine name. The URL then becomes
    `HOST.TAILNET.ts.net`. Do this BEFORE enabling Funnel.
  - The tailnet part (`TAILNET`) cannot be set freely. In the admin console (DNS page, "Rename tailnet") Tailscale offers
    a list of generated names (like `fancy-name.ts.net`) and you pick one; you cannot type your own word. I could not test
    the rename here (it would change the account), so check the admin console for the current choices.
  - Public note: Funnel needs a Let's Encrypt certificate for the name, and those are published in Certificate Transparency
    logs, so the final hostname becomes publicly searchable. That is another reason to pick a neutral machine name first.
    It reveals no IP.
- **Limits / terms.** Funnel is free on the Personal plan but has non-configurable bandwidth limits that Tailscale does
  not publish (traffic over the limit is throttled), allows only ports 443, 8443 and 10000, and needs HTTPS certificates
  and the `funnel` node attribute enabled for the tailnet (the first `funnel` command prints an admin-console link to
  switch that on). Normal Tailscale terms apply (no abuse, no high-volume content distribution). Our responses are
  about 5 KB gzipped per map, so the limit is unlikely to matter. There is no edge cache, so every request reaches the PC.
- **Client IP for the rate limiter.** Funnel is expected to pass the real client address in `X-Forwarded-For` (not verified here, no Funnel was started); the server uses it when the
  connection comes from the local proxy. `GET /api/health` returns `clients_1min` (a count only): after going live, open the
  site from the phone on mobile data and from the PC; if `clients_1min` stays at 1 while two devices are using it, Funnel
  is not sending the header and all visitors share one bucket (safe but strict). Tell the agent, it is a one-line change.
- **Switch on** (PowerShell, after starting the server):
  ```
  tailscale set --hostname=nms-atlas
  tailscale funnel --bg 8791          # public https://nms-atlas.<tailnet>.ts.net/  ->  http://127.0.0.1:8791
  tailscale funnel status
  ```
- **Switch off:**
  ```
  tailscale funnel reset              # removes the Funnel config (the server keeps running on 127.0.0.1)
  tailscale funnel status             # should say "No serve config"
  ```
  Today `tailscale funnel status` and `tailscale serve status` both say "No serve config".
  The background config survives reboots until it is reset.

## (b) Cloudflare named tunnel

- **Needs** a domain whose DNS is on Cloudflare: register one at Cloudflare Registrar (at-cost price, about $10/year for
  a .com; some other endings are cheaper) or buy elsewhere and point its name servers to Cloudflare. A free Cloudflare account.
  `cloudflared` is not installed on this PC.
- **Home IP hidden?** Yes. `cloudflared` on your PC opens only OUTBOUND connections to Cloudflare's edge. The public DNS
  name is a proxied record that resolves to Cloudflare IPs; the tunnel hostname (`<id>.cfargotunnel.com`) only resolves
  inside Cloudflare. Your router needs no open port.
- **Limits / terms.** The tunnel is free; there is no published bandwidth cap for normal web/API traffic. Cloudflare's
  self-serve terms (section 2.8) restrict serving mainly large non-HTML media through the CDN, which a small JSON API is not.
  Free-plan proxy read timeout is 100 s: the server's longest wait is 90 s, so it stays under it.
  Useful free options: a Cache Rule for `/api/map/*` (the server sends `Cache-Control: public, max-age=3600` on finished maps;
  Cloudflare only caches JSON when a Cache Rule says so), the one free rate-limiting rule, Bot Fight Mode, DDoS protection.
- **Switch on** (one time, PowerShell; admin needed only for the service step):
  ```
  winget install --id Cloudflare.cloudflared
  cloudflared tunnel login                                  # opens the browser, pick the domain
  cloudflared tunnel create nms-ondemand
  cloudflared tunnel route dns nms-ondemand maps.example.com
  ```
  `%USERPROFILE%\.cloudflared\config.yml`:
  ```
  tunnel: nms-ondemand
  credentials-file: %USERPROFILE%\.cloudflared\<tunnel-id>.json
  ingress:
    - hostname: maps.example.com
      service: http://127.0.0.1:8791
    - service: http_status:404
  ```
  Then `cloudflared tunnel run nms-ondemand` (foreground) or `cloudflared service install` (starts at boot).
- **Switch off:** stop the foreground process, or `net stop cloudflared` / `cloudflared service uninstall`. To remove it
  completely: `cloudflared tunnel delete nms-ondemand` and delete the DNS record in the dashboard.
- **Site URL:** `ondemandBase = "https://maps.example.com"`. It stays the same if the PC or the tunnel is replaced.

## (c) Cloudflare quick tunnel

- **Home IP hidden?** Yes, same outbound-only mechanism as (b), URL on `trycloudflare.com`. No account, no domain.
- **Limits / terms.** Cloudflare labels quick tunnels as for testing and development only: no uptime guarantee, a cap of
  about 200 simultaneous requests, no Cache Rules or rate-limit rules (those need your own zone).
- **Switch on:** `cloudflared tunnel --url http://127.0.0.1:8791` prints `https://<random-words>.trycloudflare.com`.
- **Switch off:** close the window or press Ctrl+C. The URL dies with it.
- **Site URL:** a new one at every start, so you would have to edit `ondemandBase` and re-publish the site each time. Only
  useful to test the full chain once from a phone.

## Go-live checklist (what the user does)

1. Start the server: double-click `ondemand\Run-OnDemand-Server.cmd` (keep the window open; it writes aggregate counts only).
2. Check locally: open `http://127.0.0.1:8791/api/health` (expect `"ok":true`).
3. Pick (a) or (b) and run its "switch on" commands above.
4. Open `<public URL>/api/health` from a phone on mobile data.
5. Put the public URL into `DV_CONFIG.ondemandBase` and re-publish the site (after the viewer button is in).
6. To stop everything: the "switch off" command first, then close the server window.

## (d) Pi relay over the tailnet (added 2026-10-24; nothing is switched on by default)

Chain: `public site -> Funnel on the Pi -> relay.py on the Pi (D:/Orca/NMS-Traffic-Logger/relay.py) -> tailnet -> this PC`.
The PC then needs no Funnel and no tunnel of its own, and the home IP is never in the path.

PC side (all off until you set two values; the loopback listener on 127.0.0.1:8791 is unchanged):
1. In `ondemand/config.local.json` (untracked, wins over `ondemand/config.json`; copy `config.local.example.json` next to `ondemand_server.py`):
   ```json
   { "tailnet_bind": "100.x.x.x", "relay_ips": ["<the Pi's tailnet IP, e.g. 100.x.y.z>"] }
   ```
   Or on the command line: `--tailnet-bind 100.x.x.x --relay-ip <Pi tailnet IP>`. Both must be Tailscale addresses
   (100.64.0.0/10 or fd7a:115c:a1e0::/48); anything else and the second listener is not started (a line says so on start-up).
   `tailnet_bind` empty or `relay_ips` empty = no second listener.
2. The second listener serves ONLY peers listed in `relay_ips`; any other peer is closed without an answer
   (`tailnet_refused` counter). Limiters, queue and cache are shared with the loopback listener.
3. The header `X-Relay-Client` (the relay's salted hash of the visitor, 18 lowercase hex digits) is used as the rate-limit key
   only when the TCP peer is in `relay_ips`; from anyone else (including loopback) it is ignored. Keys stay in memory.
4. Windows firewall (run once in an administrator PowerShell; NOT run by Claude). Replace `<PI_TAILNET_IP>`:
   ```powershell
   New-NetFirewallRule -DisplayName "NMS on-demand (Pi relay only)" -Direction Inbound -Protocol TCP -LocalPort 8791 `
     -RemoteAddress <PI_TAILNET_IP> -InterfaceAlias Tailscale -Action Allow
   ```
   Remove it again: `Remove-NetFirewallRule -DisplayName "NMS on-demand (Pi relay only)"`. A Tailscale ACL that lets only the Pi
   reach `HOSTNAME:8791` is a good second lock.

## API (all GET, JSON, safe to forward unchanged by a plain pass-through proxy)

| Route | Use |
|---|---|
| `GET /api/status/<ADDR16>` | cheap progress of one system: `status` idle/queued/generating/ready/failed, `stage` 0-4, `preset`, `rooms`, `position`, `queue`, `running`, `eta_s`, `elapsed_s`, `overdue`, `slow`, `upto_s`, `scanner_busy`, `poll_ms`, `msg` (ready-made texts). Never starts a job. The page polls it every 1-2 s. |
| `GET /api/map/<ADDR16>[?wait=S]` | the map (200), or 202 with the same status fields while it is queued/generating; `?wait=0` starts the job without holding the connection. 400/404/429/503 as before. |
| `GET /api/health` | counts only. |

The address is the job id; nothing else is kept per client. ETA table and all wording: `ondemand/eta_config.json` (rebuild the
table with `python -I ondemand/build_eta_table.py`; the server reloads the file when it changes).

## Requested maps on the site

`python -I tools/publish_ondemand_maps.py --push` merges the server's generated maps into `views/ondemand/<REGION>.json.gz` of the
atlas clone and pushes (plain fast-forward under `atlas.repo_lock`, at most once per 30 minutes). Run it by hand or as a scheduled task;
the scanner is not involved.
