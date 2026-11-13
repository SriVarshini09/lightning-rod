"""Lightning Rod hub: one FastAPI app, deployed on Replit.

  Store (opened by the cloud phone):  /s/brightcart/...
  Maya's phone (held by a judge):     /maya
  Stage control (teammate's phone):   /control
  Tap calibration (hour 0):           /calibrate
  JSON API (agent, pages, tests):     /api/...

Run locally:  python -m uvicorn hub.main:app --port 8000
Set HUB_KEY to require ?k=<key> on /maya and /control and an X-Hub-Key header on the API.
"""
from __future__ import annotations

import os
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from . import pages, repbot
from .world import World

app = FastAPI(title="Lightning Rod hub")
W = World()
HUB_KEY = os.environ.get("HUB_KEY", "")
S = pages.S


def need_key(request: Request) -> None:
    if not HUB_KEY:
        return
    got = request.headers.get("x-hub-key") or request.query_params.get("k") or ""
    if got != HUB_KEY:
        raise HTTPException(401, "Missing or wrong hub key")


async def form(request: Request) -> dict[str, list[str]]:
    return parse_qs((await request.body()).decode("utf-8", "replace"))


async def body_json(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


def html(s: str) -> HTMLResponse:
    return HTMLResponse(s, headers={"Cache-Control": "no-store"})


@app.get("/")
def home():
    return RedirectResponse(S)


# ------------------------------------------------------------------ store
@app.get(S)
def store_feed():
    return html(pages.feed(W))


@app.get(S + "/p/{sku}")
def store_product(sku: str):
    if sku not in W.products:
        raise HTTPException(404)
    return html(pages.product(W, sku))


@app.post(S + "/cart/add")
async def store_cart_add(request: Request):
    sku = (await form(request)).get("sku", [""])[0]
    if sku in W.products:
        W.cart_add(sku)
    return RedirectResponse(S + "/cart", status_code=303)


@app.post(S + "/cart/remove")
def store_cart_remove():
    W.cart_clear()
    W.add_log("store", "Cart emptied; the held price was released")
    return RedirectResponse(S, status_code=303)


@app.get(S + "/cart")
def store_cart():
    return html(pages.cart(W))


@app.get(S + "/checkout")
def store_checkout():
    return html(pages.checkout(W))


@app.post(S + "/checkout/place")
async def store_place(request: Request):
    checked = set((await form(request)).get("addon", []))
    order = W.place_order(checked)
    if not order:
        return RedirectResponse(S + "/cart", status_code=303)
    return RedirectResponse(f"{S}/order/{order['no']}", status_code=303)


@app.get(S + "/order/{no}")
def store_confirmed(no: str):
    return html(pages.confirmed(W, no))


@app.get(S + "/orders")
def store_orders():
    return html(pages.orders(W))


@app.get(S + "/orders/{no}")
def store_order(no: str):
    return html(pages.order_detail(W, no))


@app.get(S + "/chat/{no}")
def store_chat(no: str):
    return html(pages.chat(W, no))


@app.post(S + "/chat/{no}/send")
async def store_chat_send(no: str, request: Request):
    text = (await form(request)).get("text", [""])[0].strip()[:600]
    if text and W.order(no):
        W.chat_add(no, "you", text)
        decision, amount = W.refund_decision(no, text)
        words = await run_in_threadpool(repbot.reply, decision, no, amount, text)
        W.chat_add(no, "rep", words)
        W.add_log("rep", f"Support ({decision}): {words}", no=no)
        if decision == "grant":
            W.grant_refund(no, amount)
    return RedirectResponse(f"{S}/chat/{no}", status_code=303)


# ------------------------------------------------------------------ people pages
@app.get("/maya")
def maya_page(request: Request):
    need_key(request)
    return html(pages.maya(W))


@app.get("/control")
def control_page(request: Request):
    need_key(request)
    return html(pages.control(W))


@app.get("/calibrate")
def calibrate_page():
    return html(pages.calibrate(W))


# ------------------------------------------------------------------ API
@app.get("/api/world/version")
def api_version():
    return JSONResponse({"v": W.version}, headers={"Cache-Control": "no-store"})


@app.get("/api/world")
def api_world(request: Request):
    need_key(request)
    return W.public()


@app.get("/api/maya")
def api_maya(request: Request):
    need_key(request)
    s = W.public()
    s["break_clock"] = W.catalog.get("approve_clock")
    s["log"] = [l for l in s["log"] if l["kind"] in ("said", "order", "refund", "maya", "ask")][-20:]
    return s


@app.post("/api/control/fire/{beat}")
def api_fire(beat: str, request: Request):
    need_key(request)
    try:
        return W.fire(beat)
    except KeyError:
        raise HTTPException(404, f"No beat called {beat}")


@app.post("/api/control/reset")
def api_reset(request: Request):
    need_key(request)
    W.reset()
    return {"ok": True}


@app.post("/api/control/auto")
async def api_auto(request: Request):
    need_key(request)
    W.auto = bool((await body_json(request)).get("on"))
    if W.auto and W.agent["run"] and not W.awaiting:
        W.schedule_next(4.0)
    W.bump()
    return {"auto": W.auto}


@app.post("/api/agent/start")
def api_agent_start(request: Request):
    need_key(request)
    W.start_agent()
    return {"ok": True}


@app.get("/api/agent/state")
def api_agent_state(request: Request):
    need_key(request)
    return {"run": W.agent["run"], "end": W.agent["end"], "clock": W.clock}


@app.post("/api/agent/log")
async def api_agent_log(request: Request):
    need_key(request)
    b = await body_json(request)
    W.agent_event(str(b.get("kind", "note")), str(b.get("text", "")), b.get("data") or {})
    return {"ok": True}


@app.post("/api/approvals")
async def api_ask(request: Request):
    need_key(request)
    return W.ask(await body_json(request))


@app.get("/api/approvals/{aid}")
def api_approval(aid: str, request: Request):
    need_key(request)
    if aid not in W.approvals:
        raise HTTPException(404)
    return W.approvals[aid]


@app.post("/api/approvals/{aid}/answer")
async def api_answer(aid: str, request: Request):
    need_key(request)
    if aid not in W.approvals:
        raise HTTPException(404)
    return W.answer(aid, str((await body_json(request)).get("decision", "")))


@app.post("/api/calibration/hit")
async def api_cal_hit(request: Request):
    W.calib["hits"].append(await body_json(request))
    return {"ok": True}


@app.post("/api/calibration/text")
async def api_cal_text(request: Request):
    W.calib["text"] = str((await body_json(request)).get("text", ""))
    return {"ok": True}


@app.get("/api/calibration")
def api_cal(request: Request):
    need_key(request)
    return W.calib


@app.post("/api/calibration/reset")
def api_cal_reset(request: Request):
    need_key(request)
    W.calib = {"hits": [], "text": "", "viewport": None}
    return {"ok": True}
