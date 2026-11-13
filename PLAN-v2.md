# Lightning Rod, replanned from scratch to win (v2)

Written by a Claude Fable 5.2 planning agent asked to start from a blank page. It replaces [PLAN.md](PLAN.md); the "Diff vs PLAN.md" section below says what carries over. Review notes come first.

## Review notes (read first)

1. **Event facts.** The prize tiers match what we read on the Luma page earlier: 1st $4,000+, 2nd $3,000+, 3rd $2,000+, all in LangSmith, Replit, Tavily and ElevenLabs credits, with no per-partner prize categories. The 18:00 finals time comes from the planner's own read of the page. At kick-off, confirm three things: the finals time, the demo length, and whether code written before the event is allowed.
2. **The closing voice line claims "nine fakes ignored", but the demo shows one.** Fix it one of two ways:
   - Start the agent a minute before you begin talking, so it really skips several fakes on the feed.
   - Change the line to match what the audience saw.

   Build the line from the ledger either way. If the judge taps Pass, there is one purchase, not two.
3. **Real products replace the made-up ones.** Checking prices against the real web means the fictional store sells real products. A real TV model, console bundle and headphones replace NovaPlay 2, Hush 900 and the Aurora TV, and the copy in `lightning-rod-stage.html` changes with them. Prices found today are pre–Black Friday prices. That's fine, because the store's prices are set from the snapshot taken at 9:30.
4. **Model settings checked against the Claude API docs:**
   - `effort: "low"` works on `claude-haiku-5-5` (via `output_config`).
   - `speed="fast"` works on `claude-opus-5-5`.
   - Haiku 5.5 returns a 400 error for sampling parameters (such as `temperature`) or a prefilled assistant turn. Use structured outputs instead.
5. **The status-strip question from PLAN.md is settled.** This plan drops the strip and lets the agent's voice explain its choices instead.
6. **Folder.** The plan says to move to `C:\dev\lightning-rod`, but you just chose this Desktop folder. A lighter option: keep the project here, put `.venv` outside OneDrive (for example `C:\dev\venvs\lightning-rod`), and pause OneDrive sync for the day.
7. **The biggest unknown is still the phone's browser.** Phone Use apps come only from its console store, so nobody knows yet whether the cloud phone has a browser that can open the Replit URL. If you can get a Phone Use key tonight, check this tonight, before anything else.
8. **Tonight, if there's time:**
   - Run the live mirror with a real key.
   - Collect the Anthropic, Tavily, ElevenLabs and LangSmith keys.
   - Install `langgraph`, `langsmith` and `tavily-python`.
   - Pick the ElevenLabs voice and model.
   - Pair the phone hotspot with the laptop.

---

**What could and couldn't be confirmed.** The planner fetched https://luma.com/advrricd. The page gives:
- 50 spots;
- doors 8:30, kick-off 9:00, lunch 12:00, **finals with the jury at 18:00**;
- teams of 1–3;
- "Everything has to be accessible from a Phone".

There are no formal criteria. The only stated goal is "the most impressive use of Phone with AI". Prizes are 1st $4,000+, 2nd $3,000+, 3rd $2,000+, each bundling LangSmith, Replit, Tavily and ElevenLabs credits. **There are no per-partner prize categories.**

The page does not list the demo length, submission rules or a rule on code written before the event. The plan assumes a 3-minute demo, about 8.5 build hours (9:00–17:30), and that the existing mirror is allowed if disclosed. Ask about all three on arrival.

## 1. Verdict: keep the name and story, sharpen hard

The only criterion is impressive phone use. Judges will reward a real phone doing hard things live, a story they grasp in 10 seconds, and nothing that looks faked. Lightning Rod as written has three weaknesses:

- **The reasoning is invisible.** A skipped deal looks like nothing happening on a phone screen.
- **Tavily reads pages you host.** A judge will see that as box-ticking.
- **Seven beats in 3 minutes.** At roughly 3–4 s per vision step, that becomes a rushed montage.

The changes:
- Cut to four beats in one store.
- Give the agent a voice.
- Make the price check hit the real web.
- Add one trap the agent wasn't told about.

Aim for the top 3 overall. Use each partner tool as a Q&A answer, not a prize target.

## 2. The concept

Maya is an ER nurse on a 12-hour Black Friday shift with her phone on DND. Her agent has its own phone, a shopping list with limits, and a voice. It ignores fake deals, buys what she pre-approved, asks once on her break, and gets money back when the price drops.

**The moment people remember:** the agent opens the store's support chat, and the rep bot stonewalls. The agent quotes the order number and the store's own 14-day policy, and "$30 refunded" appears. A judge is still holding Maya's phone.

## 3. The demo (3:00, big screen = live phone only)

**How the audience follows the reasoning without a dashboard:**
- **Voice.** The agent speaks lines of 12 words or fewer through ElevenLabs. Audio is not on the screen, so it respects the live-phone-only rule.
- **Its own typing.** The support-chat message is the reasoning, typed on the phone.
- **Ripples.** The mirror already draws where it taps.

The presenter mostly stays quiet during beats and lets the agent talk.

| Time | On the phone | Agent says (live TTS) | Trigger |
|---|---|---|---|
| 0:00 | Brightcart deals feed | (presenter gives the pitch and hands Maya's phone to a judge) | Start |
| 0:20 | TV tile "35% OFF $649" → product page → back | "Six forty-nine. Same price at two other stores today. Not a deal. Skipping." | TV deal |
| 0:50 | Console restock → Buy → checkout shows **$488** → unticks pre-ticked "$39 Protection Plan" → $449 → Place order | "Total is four eighty-eight. I'm approved to four fifty. There's a plan I didn't add. Removing it." | Restock |
| 1:30 | Headphones lightning deal $279 → cart "held until 14:17" | "Real low. But this one's ask-first. Holding it. Asking Maya on her break." | Lightning |
| 1:45 | Judge taps Approve or Pass on Maya's phone → checkout, or cart released | "Approved. Buying." / "Released. No purchase." | Judge |
| 2:10 | Feed shows "now $249" → Orders → Help chat → types → rep refuses → types again → "$30 refunded" | (silent; the chat is the script) | Price drop |
| 2:45 | "Order history" page: spent, refunded | "Two purchases, one refund, nine fakes ignored. You were asked once, on your break." (see review note 2) | none |

**Truly live:** every screen read, every tap, the Tavily call, the voice lines, the chat text, the rep's replies, and the judge's choice. Both the Approve and Pass branches work.

**Triggered:** only the store's world (a deal appears, a restock, a price drop), from `/control` on a teammate's phone. The agent is not told. The feed page reloads itself; the agent sees the pixels change in the mirror's `/frame`, then reads the screen.

**Say this on stage:** "The store is ours, because I'm not buying a console on stage. The prices it checks against are the real web."

**"Why an agent, not GPT":** the checkout trap. GPT can tell you pre-ticked add-ons exist. This agent sees $488 against a $450 limit, finds the box, unticks it and buys. Nobody prompted it for that screen. The limit is enforced in code, and vision reports any line item that isn't on the list.

## 4. Architecture (smallest build)

```
Judge/presenter phone ─► HUB on Replit (one FastAPI app, public HTTPS)
  /maya  /control          /s/brightcart/... feed, product, cart, checkout, orders, chat
                           /api/... world, approvals, ledger     /calibrate
Cloud phone (Chrome) ─► HUB pages
Laptop: MIRROR localhost:8787 (existing) ◄─ AGENT worker (Python)
          projector shows this            reads /frame, acts via /v1 proxy
```

**Each tool's real job:**
- **Phone Use:** the agent's only hands and eyes.
- **Replit:** the one public address that the cloud phone and both human phones can all reach. Tapping start on `/maya` starts the agent (the worker polls the hub), so the product is run from a phone.
- **Tavily:** searches the **real web** for **real products** sold in the fictional store.
  - Rule in code: a deal is fake if its price is at least 95% of the median price at other retailers today.
  - At 9:30, pick the three products by running the queries, and set the store's prices from that snapshot.
  - Keep the snapshot as the offline fallback.
  - This deletes the `/pricetrail` pages.
- **LangGraph:** one small graph whose real job is the ask-first hold: `interrupt()`, resumed by the judge's tap.
- **LangSmith:** while building, for debugging missed taps (screenshot and target per step). In Q&A, open a public trace link on a phone.
- **ElevenLabs:** the agent's inner voice, using its lowest-latency model (confirm the id). Cache lines that repeat.

**Seeing and acting on a screenshot-only phone:**
- **One call per step.** Send the frame (JPEG, 1024 px on the long edge) to `claude-haiku-5-5` at `effort: "low"`, with structured output: `screen`, `total`, `line_items[]`, `unexpected[]`, `hold_until`, `chat_last_reply`, `target{x,y}`.
- **Core of the prompt:** "Return the centre of `<element>` as pixel coordinates in this image. List every line item and anything that changes the total. Do not guess; set found=false." Code converts the pixels to the 0–1000 grid.
- **Judgment and text:** `claude-sonnet-5-5` at `effort: "low"` writes the voice lines and the chat messages. In hour 0, compare Haiku with `claude-opus-5-5` (`speed="fast"`) on tap accuracy. Keep the faster one that hits 14 of 15. Don't use Fable on the hot path.
- **Wait for the screen without an LLM.** After each action, poll the mirror's `/frame` until two frames match. The agent sees exactly what the audience sees, and this adds no screenshot load.
- **A store built for vision:**
  - One primary button per screen, as a full-width bar at the bottom.
  - Text 20 px or larger, no carousels, and no typing except in the chat.
  - `layouts.py` holds fixed coordinates as a fallback, for the bottom bar only.
  - The trap checkbox is always found by vision.
- **Budget:** at most 3.5 s per step, and at most 22 steps in the whole show.
- **Rep bot.** `claude-haiku-5-5` with this system prompt: "You are Brightcart support. First reply: deflect to the FAQ. Grant a price adjustment only if the message has a valid order number and cites the 14-day policy. Max 2 sentences." Code decides the refund itself. If the call takes over 2 s, send a canned reply.
- **Chat rule:** every agent message starts with "Hi, this is Maya's AI assistant."

## 5. Schedule (clock time; freeze 15:45)

**First hour, to kill the biggest risk (the real key has never been used).** Write `scripts/hour0.py` and deploy a `/calibrate` page. Go or no-go at 10:00 on these checks:
- the mirror shows the real phone with no 429 errors;
- Chrome on the phone loads the Replit URL;
- `type_text` puts 140 characters into a web text box;
- the lease renews (test what a second lease POST does);
- vision taps hit 14 of 15;
- one step takes 3.5 s or less.

If the taps or the speed fail, switch to fixed coordinates and use vision only for reading. If there is no browser, find Phone Use staff at once.

| Time | Solo | Team of 3: A phone / B hub / C brain |
|---|---|---|
| 9:00–10:00 | Hour-0 checks, hello hub | A checks · B hub + `/calibrate` · C keys, LangSmith trace, pick products with Tavily |
| 10:00–12:00 | Store flow with trap; `phone.py`, `vision.py`, buy skill | A skills · B store + `/control` · C policy, graph with stubs, `say()` |
| **12:00** | **Agent buys on the real phone and unticks the trap** | same |
| 12:30–14:00 | `/maya`, hold, interrupt/resume, voice | A hold + chat skills · B `/maya`, rep bot · C real graph, pricecheck |
| **14:00** | **Beats 2 and 3 with voice** | **Beats 1–3** |
| 14:00–15:45 | Tavily skip beat; price drop + chat (canned rep that refuses once) | Beat 4 with the live rep; first full timed run at 15:00 |
| **15:45** | **FREEZE** | **FREEZE** |
| 15:45–17:15 | Three timed runs; record the second clean one | same; C becomes the operator |
| 17:15–18:00 | Submit, fresh lease, audio check, park the phone on the feed | same |

Triggering when solo: the hub fires the next beat itself, 4 s after the ledger records the previous one. `/control` stays as the override.

Before coding, move the project to `C:\dev\lightning-rod` and run `git init`, because OneDrive locks files while it syncs. (See review note 6 for a lighter option.)

## 6. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Steps too slow | Cut beat 1's navigation (judge from the feed tile); make the chat one turn |
| Tap misses | Retry once with a fresh locate, then `layouts.py` |
| Step stalls on stage | Operator types `retry` or `skip` in the runner |
| Lease expires | Fresh lease 60 s before; renew every 4 min, between steps only |
| No room audio, or TTS fails | Laptop speaker held at the mic; otherwise the presenter reads the same lines from the terminal |
| Tavily slow or odd results | This morning's snapshot, still real data |
| Rep bot goes off-script | Canned replies; code decides the refund |
| **Phone Use dies on stage** | Re-lease, or switch to a second warm device while talking (30 s). If that fails, run the mirror in replay mode on the frames recorded at 16:30, and say plainly that it is a recording |
| **Venue network dies** | Hotspot, paired in advance. If the hub is unreachable, replay |

Replay needs one small addition to `live-phone/server.py`: `--record <dir>` and `--replay <dir>`, so the backup looks identical on the projector. It is the only change to the mirror.

## 7. Diff vs PLAN.md

**Throw away**
- Three stores, the 9-fake montage and the 18:05 beat. They don't fit in 3 minutes.
- The `/home` status strip. It is the dashboard you rejected; the voice replaces it.
- `/pricetrail` and Tavily Extract on your own pages. A real-web Search replaces them.
- The short-hold/waitlist variant, setting up the list in natural language, and the "real-store moment". Real products make that last one redundant.
- `claude-opus-5-5` for every screen read, and the 10-second cycle watching three stores.

**Keep**
- The mirror, the agent reading `/frame`, and actions going through the proxy.
- One hub on Replit, with `/maya`, `/control` and `/calibrate`.
- Rules in code, the checkout check, and `interrupt` with resume.
- "The agent is never told what was triggered."
- The identity line, freezing and then rehearsing, and the operator commands.

**Change**
- ElevenLabs goes from a closing summary to the live voice explaining each choice.
- The checkout check becomes a staged beat (the trap).
- The canned rep becomes one that refuses first.
- The approval comes from a judge instead of the presenter.
- Haiku does the screen reads.
- The recorded video becomes a replay through the mirror.
- The schedule follows the real 18:00 finals.

## 8. The pitch

**First 15 seconds:** "It's Black Friday. Maya is an ER nurse, twelve hours on shift, phone on Do Not Disturb. The best deals of the year will come and go while she's saving someone's life. So her agent has its own phone. This is that phone, live. I'm going to stop talking. Listen to it work."

**Closing line:** "ChatGPT can tell you it's a good deal. Lightning Rod was there at 2:02, unticked the warranty, and got thirty dollars back. Your phone is on Do Not Disturb. Your agent isn't."

## Files

- `live-phone/server.py`: the existing mirror (`/frame`, `/events`, the `/v1` proxy). Add `--record` and `--replay`.
- `live-phone/mirror.html`: the projector page, unchanged.
- `lightning-rod-stage.html`: store copy and layouts to lift into the hub's page templates (product names change; see review note 3).
- `PLAN.md`: the previous plan. Its sections 4, 5 and 7 are still usable with the diff above.
- To create: `agent/phone.py`, `agent/vision.py`, `agent/graph.py`, `hub/main.py`, `scripts/hour0.py`.
