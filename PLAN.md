# Lightning Rod: hackathon build plan (Do Not Disturb Hackathon, Fri Nov 13, 2026)

> **Replaced by [PLAN-v2.md](PLAN-v2.md)**, a from-scratch replan. Its "Diff vs PLAN.md" section says what still applies here.

Written by a Claude Fable 5.2 planning agent and reviewed afterwards. The review notes come first.

## Review notes (read first)

1. **Decide: the `/home` status strip.** The plan adds a two-line status strip on the agent's phone ("Skipped Aurora 65-inch TV: same $649 on Oct 14", "Spent $449 of $750"). Without it, the price-history reasoning can't be seen on a phone-only screen. If it feels like a dashboard, keep the three store icons, drop the strip, and say the verdicts out loud.
2. **The montage won't fit its slot as written.** The run sheet gives the 8 extra fake-deal checks about 15 to 25 seconds. Checked one at a time (a screen read plus a Tavily call each), they would take 40 to 60 seconds. Fix it with one of these:
   - check a whole feed at once: one Tavily Extract call with every product's price-history URL, then one Claude call;
   - or start the shift about 60 seconds before you begin talking.
3. **Corrected package list:** Python 3.13.7 already has `anthropic` 2.4.0, `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pillow`, `jinja2` and `python-dotenv`. Only `langgraph`, `langsmith` and `tavily-python` are missing.
4. **OneDrive:** this folder is on the OneDrive Desktop. Before coding, either move it to somewhere like `C:\dev\lightning-rod` or keep `.venv` outside OneDrive, because sync locks files.
5. **Solo clicker:** the mirror page runs on `localhost` and the hub on Replit. For the PageDown handler in `mirror.html` to call the hub, the hub needs CORS for `http://localhost:8787`, or `server.py` needs a small forwarding route.

---

Read before writing: `live-phone/server.py`, `live-phone/mirror.html`, `live-phone/README.md`, and the `SCREENS` / `BEATS` objects in `lightning-rod-stage.html`. The mirror needs no redesign. Every latency figure below is a budget to measure at hour 0, not a measurement.

## 1. What gets demoed

A Phone Use cloud Android phone, mirrored full screen, shops three fictional mobile-web stores while "Maya" is on shift. It reads every screen with Claude vision and taps on its own. The presenter starts the shift and later approves one purchase from their own phone, and that phone speaks the ElevenLabs summary at the end.

- **Live:** every tap, every screen read, the price-history verdicts, the budget and rule decisions, both checkouts, the approval pause and resume, the support-chat message, the refund detection, the summary text and voice.
- **Triggered on cue:** the world only. A teammate presses buttons that jump the story clock and change the stores (restock, lightning deal, break starts, price drop, shift ends). The store's support rep is a canned reply.
- **Never faked:** the agent is not told what was triggered; it finds out by looking at the phone.

## 2. Architecture

```
 Presenter phone ──https──►  HUB (one FastAPI app on Replit, public URL)
   /maya  list, Start shift,   ├─ /home              agent's launcher: 3 store icons + status strip
          approval card, voice ├─ /s/{store}/...     Brightcart, Voltline, Northpeak (one template set)
 Operator phone ──https──►     ├─ /pricetrail/{sku}  public price-history pages (Tavily reads these)
   /control  beat buttons      ├─ /maya, /control
                               └─ /api/...           world clock, rules, approvals, ledger, summary
                                    ▲ renders in Chrome            ▲ agent polls every 1 s
 Phone Use cloud phone ◄── REST ── MIRROR localhost:8787 ◄── AGENT (laptop, Python)
        (screenshots + actions)    (existing; projector       runner.py → LangGraph graph
                                    shows this full screen)     ├─ Claude (anthropic SDK): screen reads, chat text
                                                                ├─ Tavily: price history
                                                                ├─ ElevenLabs: summary mp3 → POST to hub
                                                                └─ LangSmith: one trace per deal
```

Decisions:

- **One Replit app for everything web** (stores, Maya page, control panel, price tracker, API). One URL to open on the phone and one in-memory world state. Deploy it as a single always-on instance (Reserved VM), because in-memory state breaks with more than one instance. Fallback: run the hub on the laptop behind an ngrok tunnel.
- **The agent runs on the laptop** and only makes outbound calls, so no inbound networking is needed. It talks to Maya's page through the hub by polling.
- **The agent reads screens from the mirror's `GET /frame`**, not from Phone Use directly. The mirror already polls every 0.35 s, so this adds no screenshot load. `/frame` returns the latest bytes plus an `X-Frame-Seq` header. Actions go through `http://localhost:8787/v1/...` so ripples appear.
- **The story clock lives in the hub.** It ticks in real time and jumps when a beat button is pressed. Store pages show it in their header ("Fri Nov 27 · 14:02") so the audience sees story time on the phone.
- **`/home` needs your confirmation** (see review note 1). It is the page the agent returns to between stores, with three store icons and a two-line status strip. It mirrors the `handoff` screen in the mockup.
- **Tavily uses Extract, not Search, for the fictional products.** Search cannot find products that do not exist. `client.extract(urls=[...])` on our public `/pricetrail/{sku}` pages is a real Tavily call on controllable content. Tavily Search is used only in the optional real-store moment.

## 3. Repo layout

Add next to `live-phone/`. Run `git init` and push to a private GitHub repo that Replit imports. (See review note 4 about OneDrive.)

```
Black Friday Agent/
  live-phone/                 (existing, unchanged)
  agent/
    config.py                 env, MODEL="claude-opus-5-5", FAST_MODE, timeouts, HUB_URL, MIRROR_URL
    phone.py                  Phone Use client via mirror: lease keeper, tap/swipe/type/key/open_app, frame(), settle()
    vision.py                 read_screen(png, find=...) → ScreenRead (Pydantic), resize, unchanged-screen check
    skills.py                 open_store, read_feed, open_deal, add_to_cart, checkout, release_cart, join_waitlist, open_chat, send_chat, go_home
    layouts.py                fixed 0–1000 coordinates per known screen (fallback tap targets)
    policy.py                 pure code: rule match, budget, cap, hold-vs-break gate, checkout guard
    pricecheck.py             Tavily extract/search + Claude extraction → Evidence + verdict
    graph.py                  LangGraph StateGraph, state, nodes, edges
    hub_client.py             world, rules, approvals, ledger, summary
    ledger.py                 spent / committed / saved / fakes / orders, JSON on disk, pushed to hub
    voice.py                  summary text from ledger + ElevenLabs TTS
    runner.py                 outer watch loop, approval wait loop, operator commands
  hub/
    main.py                   FastAPI routes
    world.py                  in-memory state, clock, beats, holds, orders, chat
    templates/                home, feed, product, cart, checkout, done, chat, pricetrail, maya, control, calibrate
    static/                   style.css (brand colour as a CSS variable), small JS pollers
  scripts/
    hour0_checks.py           the go/no-go checks in section 7
    calibrate.py              tap-accuracy test against /calibrate
  .env.example  requirements.txt  .replit  README.md
```

## 4. LangGraph design

**One compiled graph, one run per event.** `runner.py` owns the endless watch loop in plain Python and invokes the graph once per event with `thread_id = event id`. This avoids the recursion limit and gives one clean LangSmith trace per deal. Checkpointer: `InMemorySaver`.

**State (TypedDict):** `kind` (deal | price_drop | shift_end), `store`, `deal` {title, price, was_price, badge}, `item_key`, `rule` {mode: preapproved | ask | real_low_only, cap}, `budget` {total, spent, committed}, `evidence` {points, min_90d, sources, verdict}, `decision`, `reason`, `hold_expires_at`, `break_start`, `approval_id`, `approval`, `order` {id, total, arrives}, `refund`, `errors`.

**Nodes and edges:**

```
START ─route(kind)─┬─ deal ──► match_item ──(not on list)──► record
                   │            └► verify_price (Tavily + Claude extract; verdict in code)
                   │                └► decide (policy.py, no LLM)
                   │                     ├ skip (fake / over cap / over budget) ──► record
                   │                     ├ buy_now ──► add_to_cart ──► guard_checkout ──► place_order ──► record
                   │                     └ ask_first ──► add_to_cart ──► hold_gate
                   │                            ├ hold ends before break ──► release_and_waitlist ──► record
                   │                            └ else ──► request_approval ──► await_approval (interrupt)
                   │                                   ├ buy ──► guard_checkout ──► place_order ──► record
                   │                                   └ skip / expired ──► release_and_waitlist ──► record
                   ├─ price_drop ──► open_chat ──► compose_message ──► send ──► read_reply ──► record
                   └─ shift_end ──► summarize ──► speak ──► record
```

- **Fake-deal verdict (code):** real only if the price is at most 90% of the lowest price in the last 90 days. TV: $649 now, $649 on Oct 14 → fake. Hush 900: $279 against a $328 low → real. Claude only extracts the price points from the Tavily content.
- **Budget (code, in `decide` and again in `guard_checkout`):** `spent + committed + price <= budget` and `price <= rule.cap`. A held cart counts as committed.
- **Checkout guard:** right before "Place order", re-read the checkout screen. The total must equal the expected price, "Pay with" must show a saved card, and the screen must not ask for a card number. Any mismatch aborts. Purchase skills run only on the hub's host.
- **Approval pause:** `request_approval` POSTs the card to the hub with `visible_at = break_start`. Maya's page shows it only once the story clock reaches 14:15; nothing is ever pushed. `await_approval` contains only `interrupt(...)`, because LangGraph re-runs that node from the top on resume.
- **Resume:** `runner.py` polls the hub every 1 s. On a decision it calls `graph.invoke(Command(resume={"decision": "buy"}), config)`. If the story clock passes `hold_expires_at` first, it resumes with `"expired"`.
- **Hold rule:** `hold_gate` compares the hold expiry read from the cart screen with `break_start + 1 min`. In the demo the hold lasts until 14:17 and the break is 14:15, so it waits. A "short hold" trigger (ends 14:10) makes the agent empty the cart and tap "Join waitlist"; keep that for Q&A.
- **Identity rule:** `compose_message` output must start with "Hi, this is Maya's AI assistant." Code checks this and prepends it if missing.
- **Phone parking:** the runner is single-threaded. While an approval is pending the phone stays on the cart page showing the hold.
- **Tracing:** set `LANGSMITH_TRACING=true`; LangGraph traces itself. Put `@traceable` on `read_screen`, `pricecheck` and each skill. Try `wrap_anthropic` on the client, but whether it wraps `messages.parse` is unverified, so `@traceable` is the guarantee.

**Screen reading and tap targets**

- One call shape everywhere: `client.messages.parse(model=MODEL, max_tokens=2000, output_config={"effort": "low"}, messages=[image + instruction], output_format=ScreenRead)`, read `.parsed_output`. Check `stop_reason` for `refusal` first.
- `ScreenRead` is one schema with optional parts: `screen` type, `deals[]` (each with a tap point), `product`, `cart` (with `hold_until`), `checkout` (total, pay_with, asks_card_number), `order`, `chat_last_reply`, and `target {found, x, y}` for the element named in `find=`.
- Claude returns the centre of the named element on the 0–1000 grid. Resize the image to 1024 px on the long edge first; the grid is normalised, so resizing is safe.
- After each action, `settle()` polls `/frame` every 150 ms until two consecutive frames match (3 s timeout). This costs no Claude call.
- If the screen did not change after a tap, retry once with a fresh locate, then use `layouts.py`. Every store page has its main button as a full-width bar fixed at the bottom, as in the mockup's taps at (500, 930), so fixed coordinates are reliable.
- Spend Claude calls only at decision points: feed read, product read, cart hold, checkout guard, confirmation, chat reply. Target at most 3 calls per beat.
- Unchanged-screen skip: downscale to 64×128 grey with the top 6% cropped, compare with the last read of that page, and skip the Claude call if nothing moved. This keeps the watch cycle around 10 s across three stores.
- Speed levers, in order: `speed="fast"` on `claude-opus-5-5`, 768 px images, then `claude-haiku-5-5` for reads only.

## 5. The fake store (hub)

- **Pages per store**, server-rendered so Back works: feed `/s/{store}/`, product `/p/{sku}`, cart, checkout ("Pay with: Saved card ending 0417" is display text; there is no card field anywhere), order done, orders, help chat. Take copy and layout from `SCREENS` in `lightning-rod-stage.html`.
- **Seeded so the numbers come out right:** Brightcart doorbuster TV (1 fake), Voltline 4 tiles (4 fake), Northpeak 4 lightning deals (4 fake) = 9. Each has a `/pricetrail/{sku}` page with dated prices. Feed pages have no ticking timers, so the unchanged-screen skip works.
- **Live updates:** each page polls `/api/version` every 1 s and reloads when it changes. The agent never needs to reload.
- **Control panel `/control`** (PIN-protected, sized for a phone). Each button sets the clock and changes the world:
  - Reset · 06:00 Start
  - 12:30 Restock NovaPlay ($449, "Only 3 left")
  - 14:02 Lightning Hush 900 ($279, hold 15 min) · variant: short hold
  - 14:15 Break starts
  - 16:40 Price drop to $249
  - 18:05 Shift ends
  - Extras: Sold out, Slow rep
- **Hold:** adding a lightning item to the cart sets `hold_expires = clock + 15 min`; the cart shows "Deal price held until 14:17".
- **Support chat:** a message containing the order number gets a canned rep reply after 1.5 s, and the hub marks the order refunded $30. A Claude-powered rep is a stretch.
- **Price-drop detection:** the Northpeak feed shows a "PRICE DROPPED · Hush 900 · $249" tile. The agent reads it and matches it against its orders.
- **Maya page `/maya`:** the list (3 items prefilled, editable caps and modes), budget, break time from a seeded calendar entry, and one big "Turn on Do Not Disturb" button that starts the agent. Later it shows the approval card (Buy / Skip) and the end-of-shift card with a Play button. Audio must start from a tap on phones.
- **Reaching it:** `open_app com.android.chrome`, tap the address bar, `type_text` the Replit URL, `enter`, once at the start. After that it is taps and Back only. A human clears Chrome's first-run screens once in the Phone Use console.
- **`/calibrate`:** five labelled buttons, and the page logs where taps land to `/api/taplog`. Used at hour 0 and for debugging.

## 6. Schedule (T = start; freeze at T+8:00)

**Team of 3.** A = phone and skills. B = hub, in Replit. C = graph, policy, Tavily, voice, then demo operator.

| Time | A (phone) | B (world) | C (brain) |
|---|---|---|---|
| 0:00–1:00 | Hour-0 checks, mirror live | Hub skeleton deployed, `/calibrate` | Freeze the API contract, env, LangSmith hello trace |
| **1:00 checkpoint** | Phone shows the Replit page; contract agreed | | |
| 1:00–3:00 | `phone.py`, `vision.py`, buy skill | Voltline: feed to order done; `/control` restock | `policy.py`, `ledger.py`, graph with stubbed skills |
| **3:00 checkpoint** | Agent buys the NovaPlay on the phone from a script | | |
| 3:00–5:00 | Hold, release, waitlist, chat skills | Northpeak + hold, Brightcart, `/maya`, approvals API | Real skills in the graph, interrupt/resume, `pricecheck.py` |
| **5:00 checkpoint** | Restock buy and hold → approve → buy, through the graph | | |
| 5:00–6:30 | Watch loop, unchanged-screen skip, retries | Price drop, chat rep, `/pricetrail`, `/home` strip | Refund branch, `voice.py`, summary upload |
| **6:30 checkpoint** | First full run, timed | | |
| 6:30–8:00 | Speed and reliability fixes only | Polish copy and fonts for the projector | Run sheet, rehearse triggers, real-store moment if green |
| **8:00 FREEZE** | No new features. Bug fixes only. | | |
| 8:00–9:15 | Three full rehearsals; record the backup video on the second clean run | | |
| 9:15–10:00 | Submission, fresh lease, charge phones, buffer | | |

**Solo.** Same order, narrower scope: one store template with three skins, canned chat, no real-store moment.

| Time | Work |
|---|---|
| 0:00–0:45 | Hour-0 checks |
| 0:45–2:15 | Hub: Voltline flow and `/control` |
| 2:15–4:00 | `phone.py`, `vision.py`, buy skill. **4:00 checkpoint: purchase on the phone** |
| 4:00–6:00 | Graph, policy, Northpeak hold, `/maya` approval. **6:00 checkpoint: hold → approve → buy** |
| 6:00–6:45 | Tavily and the fake TV |
| 6:45–7:30 | Price drop and chat |
| 7:30–8:00 | ElevenLabs summary. **8:00 FREEZE** |
| 8:00–10:00 | Rehearse, record backup, submit |

Solo triggering: add a key handler to `mirror.html` so a presentation clicker (PageDown) calls the hub's "next beat". It is about five lines and the only mirror change in this plan (see review note 5 about CORS).

## 7. Hour-0 checklist

| # | Check | Go when | Fallback |
|---|---|---|---|
| 1 | Rules on pre-written code | Organisers allow the mirror as a pre-built tool | Disclose it; otherwise rebuild a minimal version (about 45 min) |
| 2 | Phones or credits provided | `GET /v1/devices` lists an online phone | Own account ($0.024/min is about $14 for 10 h); last resort a personal Android over adb |
| 3 | Mirror live | Picture lags under 1 s, no 429 in 2 min at 0.35 s | `--interval 0.6`, then 1.0; or project the Phone Use console view and lose ripples |
| 4 | Browser on the phone | `open_app com.android.chrome` opens | Install any browser from the console store; ask Phone Use staff. No browser at all blocks the project |
| 5 | Open a URL and type | Address bar + `type_text` + enter loads the hub; "Maya's" types correctly; 200 characters in under 5 s | Shorter chat message; a paste-friendly link page on `/home` |
| 6 | Lease | Acquire works; note `expiresAt`; test actions without `leaseId`; test a second POST while held | Lease keeper releases and re-acquires at 8 min, only between steps; always take a fresh lease 60 s before the demo |
| 7 | Tap accuracy | Claude-located taps hit 14 of 15 on `/calibrate` | Fixed coordinates from `layouts.py` on all store pages |
| 8 | Vision latency | 10 product-page reads: median ≤ 4 s, worst ≤ 8 s | Fast mode, 768 px, then Haiku for reads |
| 9 | Action latency | Tap to changed frame ≤ 1.5 s | Longer settle; fewer steps per beat |
| 10 | Tavily Extract on the Replit URL | Content back in ≤ 3 s | Fetch the page directly with httpx and say so; keep Tavily for the real-store moment |
| 11 | ElevenLabs | mp3 in ≤ 3 s, audible from the presenter phone at the mic | Laptop speakers; browser `speechSynthesis` |
| 12 | LangSmith | Hello-graph trace appears | `@traceable` only; do not debug during the event |
| 13 | Replit | Stable URL, state survives 10 min idle | Laptop + ngrok |
| 14 | Venue | Wi-Fi reaches Phone Use and Anthropic; projector works | Phone hotspot; bring adapters |

## 8. Demo run sheet (3:00)

Before going on: Reset; phone parked on `/home`; fresh lease; mirror full screen (F); `/maya` open on the presenter phone; `/control` on the operator phone; backup video paused in a second window.

| Time | Presenter says | Operator | Big screen (agent's phone) |
|---|---|---|---|
| 0:00 | "Maya is an ER nurse. Twelve-hour shift on Black Friday, phone in her locker. Her list: a NovaPlay for her son, pre-approved to $450. Headphones for her brother, ask first. A TV only at a real low price. Budget $750." Taps **Do Not Disturb** on own phone, held up. | 06:00 Start | `/home`: "Watching 3 stores" |
| 0:20 | "09:14. Brightcart says 50% off a TV. The agent checks the price history: same $649 in October. Fake. Skipped." | none | Brightcart feed → TV page → back; strip shows the verdict |
| 0:45 | "It does that all morning. Nine fake discounts skipped, each with evidence." | none | Voltline and Northpeak feeds; counter reaches 9 |
| 1:00 | "12:30. The NovaPlay is back, $449, three left. It's pre-approved, so nobody gets asked. Saved card only; it never types a card number." | 12:30 Restock | Product → cart → checkout → "Order placed" |
| 1:30 | "14:02. Lightning deal on the headphones, $279, and this one is real. But it's ask-first. The hold lasts until 14:17 and her break is 14:15, so it holds and waits. Her phone stays silent." | 14:02 Lightning | Northpeak product → cart, "held until 14:17" |
| 1:50 | "14:15. Break. One card is waiting. Nothing rang." Taps **Buy**. | 14:15 Break | Checkout → "Order placed" |
| 2:10 | "16:40. The price drops to $249. The agent opens support chat, says who it is, and asks for the difference." | 16:40 Price drop | Chat: "Hi, this is Maya's AI assistant…" → "$30 refunded" |
| 2:40 | "18:05. Shift over." Taps **Play**, phone to the mic. Then: "Lightning Rod. It catches the deals. You keep your day." | 18:05 Shift ends | `/home`: spent $698 of $750, 9 skipped, $30 back |

The summary is built from the ledger, so it says what actually happened. If the montage is cut, the count will be lower; adjust the narration, do not hardcode 9. (See review note 2 about the montage timing.)

**Backup, in order:**
1. A step stalls: the operator types a command in the runner (`retry`, `skip`, `buy novaplay`) and the run stays live.
2. The phone or network dies: switch to the recorded run at the same beat and keep narrating.
3. Last resort: `lightning-rod-stage.html`.

## 9. Risks and cut list

| Risk | Mitigation |
|---|---|
| Screen reads too slow for 3 minutes | At most 3 Claude calls per beat, settle without Claude, fast mode, Haiku for reads |
| Tap misses | Bottom-bar buttons, retry once, fixed coordinates |
| Detection lags after a trigger | Watch cycle about 10 s; narration covers it; operator triggers one sentence early |
| Lease expires mid-demo | Fresh lease 60 s before; keeper at 8 min |
| Screenshot rate limits | Agent reads from the mirror; raise `--interval` |
| Replit sleeps or loses state | Always-on single instance; Reset rebuilds everything; ngrok fallback |
| Chrome pop-ups (translate, sign-in) | Clear them by hand once; `ScreenRead.screen = blocker` pauses and alerts the operator |
| Venue Wi-Fi | Hotspot; laptop needs outbound only |
| Agent crash while holding | Runner restart re-reads pending approvals and the ledger from the hub (only if time; otherwise use backup 2) |

**Cut first, in this order:**
1. Real-store moment
2. Natural-language list setup and voice approval
3. Short-hold / waitlist variant (keep the code path, drop the trigger)
4. `/home` status strip
5. Montage (the count drops to 1)
6. Three stores → one host with three skins and a single feed
7. Claude-located taps → fixed coordinates only
8. Live chat typing → shorter message
9. ElevenLabs → browser speech

Never cut: the live pre-approved purchase, the approval from the presenter's phone, the mirror.

## 10. Tonight

Check the hackathon rules first; tonight is accounts, keys, reading and smoke tests, with no project code.

- **Phone Use:** create the account and pay for one cloud phone. Run `python live-phone/server.py` with the real key. Run hour-0 checks 3 to 6 by hand with curl. This removes the biggest unknown.
- **Keys into `.env`:** `PHONEUSE_API_KEY`, `PHONEUSE_DEVICE_ID`, `ANTHROPIC_API_KEY` (confirm `claude-opus-5-5` access), `LANGSMITH_API_KEY`, `TAVILY_API_KEY`, `ELEVENLABS_API_KEY` plus a chosen voice id.
- **Replit:** deploy a hello FastAPI app, confirm the always-on option and a stable URL. Create an ngrok account as the fallback.
- **Python:** 3.13.7 is installed with `anthropic` 2.4.0, `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pillow`, `jinja2` and `python-dotenv`. Still missing: `langgraph`, `langsmith`, `tavily-python`. Install them in a venv outside OneDrive and confirm they import.
- **Read:** LangGraph `interrupt` and `Command(resume=...)`; Tavily Extract; ElevenLabs text-to-speech (confirm the model id); Phone Use lease docs.
- **Decide:** whether the `/home` status strip is acceptable; which real store page to use for the optional moment (one that loads without a bot wall; read-only, no login, no cart).
- **Pack:** HDMI and USB-C adapters, chargers, a clicker if solo, hotspot.
- **Ask the organisers on arrival:** is pre-written code allowed, are phones and credits provided, how long is the demo slot, and is there room audio.

**Must be built tomorrow:** everything in `agent/`, `hub/` and `scripts/`.

### Files the build starts from
- `live-phone/server.py`: the existing mirror. `/frame`, `/events` and the `/v1` proxy are what `agent/phone.py` builds on.
- `lightning-rod-stage.html`: `SCREENS` and `BEATS` hold the copy, layouts and seed data for the hub templates.
- `agent/graph.py`, `agent/phone.py`, `hub/main.py`: to create (state, nodes, interrupt/resume; Phone Use client via the mirror; stores, control panel, Maya page, approvals API).
