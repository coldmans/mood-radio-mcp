# Mac Mini Deployment

This runbook is for hosting Song Mailbox MCP on a Mac mini with `uv`, `launchd`, and a public tunnel.

## Runtime Service

Clone the repository on the Mac mini:

```bash
mkdir -p ~/GitHub
git clone https://github.com/coldmans/mood-radio-mcp.git ~/GitHub/mood-radio-mcp
cd ~/GitHub/mood-radio-mcp
mkdir -p data logs
uv sync --python 3.13 --extra dev
```

Run once for a smoke check:

```bash
PORT=8787 \
MOOD_RADIO_DB="$PWD/data/mood-radio.sqlite" \
uv run --python 3.13 mood-radio-mcp
```

The service should expose:

```text
http://127.0.0.1:8787/
http://127.0.0.1:8787/health
http://127.0.0.1:8787/mcp
```

For persistent login startup, create `~/Library/LaunchAgents/com.moodradio.mcp.plist` with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.moodradio.mcp</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/uv</string>
    <string>run</string>
    <string>--python</string>
    <string>3.13</string>
    <string>mood-radio-mcp</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/molteuhyeong/GitHub/mood-radio-mcp</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PORT</key>
    <string>8787</string>
    <key>MOOD_RADIO_DB</key>
    <string>/Users/molteuhyeong/GitHub/mood-radio-mcp/data/mood-radio.sqlite</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/molteuhyeong/GitHub/mood-radio-mcp/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/molteuhyeong/GitHub/mood-radio-mcp/logs/launchd.err.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.moodradio.mcp.plist 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.moodradio.mcp.plist
launchctl kickstart -k "gui/$(id -u)/com.moodradio.mcp"
```

## Public Endpoint Options

Tailnet-internal endpoint verified on the Mac mini:

```text
http://100.105.154.87:8787/mcp
http://macmini.taild33a67.ts.net:8787/mcp
```

This is useful for development from devices logged into the same Tailscale tailnet, but it is not enough for PlayMCP review because external PlayMCP servers are not inside the tailnet.

Preferred stable option:

```bash
tailscale funnel --bg --yes 8787
tailscale funnel status
```

Current verified public endpoint:

```text
https://macmini.taild33a67.ts.net/mcp
```

This requires Funnel to be enabled for the tailnet.
If the CLI prints an enablement URL such as `https://login.tailscale.com/f/funnel?...`, open it once as the tailnet owner/admin, enable Funnel, then rerun the command above.

Tailnet-only Tailscale Serve option:

```bash
tailscale serve --bg --yes http://127.0.0.1:8787
tailscale serve status
```

This also requires Serve to be enabled for the tailnet. If the CLI prints `https://login.tailscale.com/f/serve?...`, approve it once, then rerun the command.

Temporary Cloudflare quick tunnel option:

```bash
tmux new-session -d -s mood-radio-quick-tunnel \
  "/opt/homebrew/bin/cloudflared tunnel --config /dev/null --url http://localhost:8787 > ~/.cloudflared/mood-radio-quick-tunnel.log 2>&1"

grep -Eo 'https://[-a-zA-Z0-9.]+trycloudflare.com' ~/.cloudflared/mood-radio-quick-tunnel.log | tail -n 1
```

Quick tunnel URLs change when the tunnel process restarts, so use this only for temporary PlayMCP testing.

## Verification

From another machine:

```bash
uv run --python 3.11 python scripts/preflight_endpoint.py https://<public-endpoint>
```

Register only:

```text
https://<public-endpoint>/mcp
```
