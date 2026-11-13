# Lightning Rod

*Your phone is on Do Not Disturb. Your agent isn't.*

Maya is an ER nurse on a 12-hour Black Friday shift with her phone on Do Not Disturb. Her agent has its own phone (a Phone Use cloud phone), her shopping list with limits, and a voice. During the shift it:
- skips fake deals,
- buys what she pre-approved,
- asks her once, on her break,
- gets money back when a price drops.

This is the build of [PLAN-v2.md](PLAN-v2.md). The big screen shows only the live phone.

## What's here

| Folder | What it is | Runs on |
|---|---|---|
| `hub/` | One FastAPI app with four parts: the Brightcart store the phone opens, `/maya` (the judge holds this), `/control` (a teammate's trigger buttons) and `/calibrate` | Replit |
| `agent/` | The agent: reads the screen (Claude), decides (LangGraph + rules in code), checks prices (Tavily), talks (ElevenLabs), taps (Phone Use) | Presenting laptop |
| `live-phone/` | The projector view: the phone full screen with tap ripples. It also passes the agent's Phone Use calls through, and can record and replay a run | Presenting laptop |
| `simphone/` | A **test** phone: a phone-sized Chrome that answers the same calls as Phone Use, so you can rehearse with no keys | Laptop, tests only |
| `scripts/` | `hour0.py` (go/no-go checks), `pick_products.py` (9:30 real prices), `run_local.py` (start everything) | Laptop |
| `tests/run_sim_demo.py` | The whole show end to end, offline, with checks | Laptop |
| `data/` | The store's products and beats, Maya's list, the price snapshot | Both |

## Rehearse right now (no keys)

Terminal 1:

```bash
python scripts/run_local.py
```

Terminal 2:

```bash
python -m agent.runner --sim
```

Then:
1. Open http://localhost:8787 (the projector view; press F) and http://localhost:8000/maya.
2. Tap **Start my shift**.
3. On http://localhost:8000/control, fire beats 1–4 and then End, or turn on **Solo auto mode**.
4. Approve or Pass on `/maya` when the agent asks.

The page shows **TEST · Local test phone, not Phone Use**. In this mode the agent reads the page's HTML instead of calling Claude. That test mode only works with the test phone, never with the real one.

Automatic check of the whole show (about 1 minute):

```bash
python tests/run_sim_demo.py
```

```bash
python tests/run_sim_demo.py --pass
```

## Tonight, with keys

1. Copy `.env.example` to `.env` and fill it in.
2. Install the laptop packages:
   ```bash
   python -m pip install -r requirements-laptop.txt
   ```
3. **Hub on Replit:**
   - Upload this folder. `.replit` runs `uvicorn hub.main:app` on port 8000.
   - Optional: set `ANTHROPIC_API_KEY` in Replit Secrets so the support bot writes its own replies. Without it, it uses canned replies.
   - Put the Replit URL in `.env` as `HUB_URL`.
4. **Projector view on the real phone:**
   ```bash
   python scripts/run_local.py --live
   ```
   This starts a local copy of the hub too. The agent uses `HUB_URL` from `.env`, which is the Replit one.
5. **Hour-0 checks**, the biggest risk:
   ```bash
   python scripts/hour0.py
   ```
   - It opens `HUB_URL/calibrate` in the phone's browser, taps 15 numbered targets, types 140 characters and tests the lease.
   - It prints **GO**, or the fallback for each failure.
   - It writes `data/calibration.json` for the fixed-point tap fallback.

## 9:30 at the event

```bash
python scripts/pick_products.py --write
```

This looks up today's real prices with Tavily, saves the offline snapshot and suggests the beat prices. Then edit `data/catalog.json` by hand:
- **Product names.** They must stay matched by `data/shopping_list.json`.
- **Beat prices.** The TV's deal price should equal the real median (so it's fake). The headphones' lightning price should be real low and under $300.

## On stage

1. Start the projector view with a recording:
   ```bash
   python live-phone/server.py --record runs/take1
   ```
   Open http://localhost:8787 and press F.
2. Start the agent:
   ```bash
   python -m agent.runner
   ```
   It waits for **Start my shift** on `/maya`.
3. Hand the judge Maya's phone, open on `HUB_URL/maya`.
4. Your teammate fires beats from `HUB_URL/control`. Solo: turn on **Solo auto mode**, and each beat fires 4 s after the agent finishes the last one.
5. **Operator keys** in the agent's terminal: `p` pause · `r` resume · `s` skip this step · `retry` · `q` quit. A failed step retries once by itself.
6. **Backup if Phone Use or the network dies:**
   ```bash
   python live-phone/server.py --replay runs/take1
   ```
   The page says **RECORDED**, so say plainly that it's a recording. Press R to restart it.
7. If you set `HUB_KEY`, open `/maya?k=<key>` and `/control?k=<key>`.

## How the agent works

- **Watching costs nothing.** The agent compares screenshots pixel by pixel and calls Claude only when the screen changes.
- **One Claude call per step** (`claude-haiku-5-5`, effort low, structured output) reads the screen and finds the next thing to tap. The pixel position is converted to Phone Use's 0–1000 grid.
- **Rules are code** (`agent/policy.py`):
  - A deal is fake if it's at least 95% of the median price at other retailers.
  - The total budget is $750, and each item has its own limit.
  - The checkout check unticks anything Maya didn't ask for and pays only when the total matches the item.
- **LangGraph** (`agent/graph.py`) runs one graph per event. `interrupt()` holds the headphones until the judge answers on `/maya`.
- **LangSmith** traces each event and each Claude call when `LANGSMITH_API_KEY` is set.
- **Words:**
  - Chat messages are written by `claude-sonnet-5-5` and always start with "Hi, this is Maya's AI assistant." A template takes over if Claude fails.
  - The support rep's refund decision is made by code in `hub/world.py`. Claude only words the reply.

## What has and hasn't been verified

**Verified on this laptop:**
- The full show on the test phone: both endings (Approve: 10/10 checks; Pass: 8/8).
- `hour0.py` on the test phone (GO).
- The Claude vision request, against a fake local API: model, effort, JSON schema, image size and pixel-to-grid conversion.

**Not verified yet, because there are no keys on this laptop:**
- the real Phone Use phone (browser, taps, lease renewal, `type_text`);
- real Claude vision accuracy and speed;
- Tavily results;
- ElevenLabs audio;
- LangSmith traces.

`hour0.py` exists for the first item: run it as soon as you have a Phone Use key.
