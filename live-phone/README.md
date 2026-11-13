# Live phone on screen

Shows the Phone Use cloud phone full screen on the projector, live, with a ripple wherever the agent taps. No dashboard, nothing else on screen.

Two files, Python standard library only: `server.py` and `mirror.html`.

## Try it now (no key needed)

```bash
python server.py --mock
```

Open http://localhost:8787. You'll see a fake test phone with a fake tap and swipe every few seconds.

## Run it with the real phone

macOS / Linux:

```bash
export PHONEUSE_API_KEY="pbk_..."
python server.py
```

Windows PowerShell:

```powershell
$env:PHONEUSE_API_KEY = "pbk_..."
python server.py
```

It lists the phones your key can see and mirrors the first one. To choose a phone, add `--device <deviceId>`.

Open http://localhost:8787 and press **F** for full screen.
- **L** hides or shows the small LIVE label.
- The mouse cursor hides itself after 2 seconds.

## Make the agent's taps visible

The mirror only draws ripples for taps it sees. Send the agent's Phone Use calls through the mirror, which passes them on to Phone Use unchanged:

| The agent uses | Change this | To this |
|---|---|---|
| MCP (e.g. LangChain MCP tools) | `https://mcp.phoneuse.com/mcp` | `http://localhost:8787/mcp` |
| REST API | `https://mcp.phoneuse.com` | `http://localhost:8787` |
| Neither | after each tap, `POST http://localhost:8787/tap` with `{"x": 500, "y": 930}` | |

The agent still sends its own API key. The mirror never adds its key to forwarded calls; it only uses its key to fetch screenshots.

## On stage

- Run the mirror on the presenting laptop, open it in Chrome and press F.
- Turn off the laptop's notifications.
- The picture updates about 2 to 3 times a second, because it is built from screenshots. If Phone Use rate-limits it, the page says so. Slow it down with `--interval 0.6`.
- The Phone Use docs also name a live video route (`POST /v1/devices/{id}/stream`), which isn't used here because its format wasn't documented. If the Phone Use console has a smoother live view, compare the two on the projector and keep the better one.
- Record a screen video of one full successful run as a backup.

## On Replit

```bash
python server.py --host 0.0.0.0
```

Anyone with the Replit URL can see the phone screen, so don't share the link.
