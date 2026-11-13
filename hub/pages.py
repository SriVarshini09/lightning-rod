"""HTML for the store (seen by the agent through the phone), Maya's phone, /control and /calibrate.

The store is built to be read from a screenshot: big text, one primary action per screen
as a full-width bar at the bottom, no carousels. Elements carry data-v attributes; the
real agent never sees them (it only gets pixels), but the local test phone uses them.
"""
from __future__ import annotations

import json
from html import escape as e

from .world import World, money

S = "/s/brightcart"

STORE_CSS = """
:root{--brand:#ff7a3d;--ink:#151a22;--muted:#5b6472;--bg:#f6f4f1;--line:#e6e1da;--ok:#0b7a50}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:20px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink);padding-bottom:120px}
.top{position:sticky;top:0;z-index:5}
header{background:var(--brand);color:#fff;padding:14px 18px 12px;display:flex;justify-content:space-between;align-items:baseline}
.brand{font-weight:800;font-size:28px;letter-spacing:-.01em}
.clock{font-size:19px;opacity:.92}
nav{display:flex;gap:10px;padding:10px 14px;background:#fff;border-bottom:1px solid var(--line)}
nav a{flex:1;text-align:center;padding:12px 0;border-radius:12px;background:#f1ede8;color:var(--ink);font-weight:700;text-decoration:none;font-size:20px}
nav a.on{background:var(--ink);color:#fff}
main{padding:14px}
h1{font-size:26px;margin:4px 0 12px}
.tile{display:flex;gap:14px;align-items:center;background:#fff;border-radius:18px;padding:14px;margin-bottom:12px;text-decoration:none;color:inherit;border:1px solid var(--line)}
.pic{width:84px;height:84px;border-radius:14px;display:grid;place-items:center;font-size:48px;background:#fff1e8;flex:none}
.pic.big{width:100%;height:220px;font-size:130px;border-radius:20px;margin-bottom:14px}
.badge{display:inline-block;font-size:16px;font-weight:800;letter-spacing:.03em;padding:4px 9px;border-radius:8px;background:#ffe2d2;color:#b8430e}
.badge.lightning{background:#1f1a3d;color:#ffd84d}.badge.restock{background:#dff5ea;color:var(--ok)}.badge.drop{background:#e3f0ff;color:#1856b8}
.title{font-weight:700;font-size:21px;margin:6px 0 4px}
.price{font-size:26px;font-weight:800}.price.huge{font-size:40px}
.was{color:var(--muted);text-decoration:line-through;font-size:19px;margin-left:8px}
.muted{color:var(--muted)}
.bar{position:fixed;left:0;right:0;bottom:0;padding:12px 14px 14px;background:#fff;border-top:1px solid var(--line)}
.bar form{margin:0}
.bar button,.bar a.btn{display:block;width:100%;padding:20px 0;border:0;border-radius:16px;background:var(--brand);color:#fff;font:800 24px system-ui,sans-serif;text-align:center;text-decoration:none}
.row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px;background:#fff;border-radius:14px;margin-bottom:10px;border:1px solid var(--line)}
.check{display:flex;gap:14px;align-items:center;cursor:pointer}
.check input{width:36px;height:36px;accent-color:var(--brand);flex:none}
.total{display:flex;justify-content:space-between;font-size:28px;font-weight:800;padding:14px 4px}
.notice{background:#1f1a3d;color:#ffd84d;border-radius:14px;padding:14px 16px;font-weight:700;margin:12px 0}
.ok{background:#dff5ea;color:var(--ok);border-radius:14px;padding:16px;font-weight:800;font-size:24px;margin:12px 0;text-align:center}
.link{background:none;border:0;color:#b8430e;font:700 19px system-ui,sans-serif;padding:8px 0;text-decoration:underline}
.msgs{display:flex;flex-direction:column;gap:10px;padding-bottom:40px}
.msg{max-width:86%;padding:12px 15px;border-radius:18px;font-size:19px}
.msg.you{align-self:flex-end;background:var(--ink);color:#fff;border-bottom-right-radius:6px}
.msg.rep{align-self:flex-start;background:#fff;border:1px solid var(--line);border-bottom-left-radius:6px}
.msg.system{align-self:center;background:#dff5ea;color:var(--ok);font-weight:800;font-size:22px}
.who{font-size:14px;font-weight:700;opacity:.7;margin-bottom:2px}
.chatbar{display:flex;gap:10px;align-items:stretch}
.chatbar textarea{flex:1;font:19px system-ui,sans-serif;padding:12px;border-radius:14px;border:2px solid var(--line);resize:none;height:84px}
.chatbar button{width:118px;flex:none;padding:0}
"""


def store_page(w: World, screen: str, title: str, body: str, bar: str = "", nav: str = "",
               reload: bool = False, attrs: str = "") -> str:
    tabs = "".join(
        f'<a href="{href}" data-v="{key}" class="{"on" if nav == key else ""}">{label}</a>'
        for key, href, label in (("nav_deals", S, "Deals"), ("nav_cart", f"{S}/cart", "Cart"),
                                 ("nav_orders", f"{S}/orders", "Orders"))
    )
    script = ""
    if reload:
        script = (
            f"<script>const V={w.version};setInterval(async()=>{{try{{const r=await fetch('/api/world/version',"
            "{cache:'no-store'});const j=await r.json();if(j.v!==V)location.reload()}catch(_){}},1000)</script>"
        )
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)} · Brightcart</title>
<style>{STORE_CSS}</style></head>
<body data-screen="{screen}" {attrs}>
<div class="top"><header><span class="brand">Brightcart</span><span class="clock">Black Friday · {e(w.clock)}</span></header>
<nav>{tabs}</nav></div>
<main>{body}</main>
{f'<div class="bar">{bar}</div>' if bar else ''}
{script}
</body></html>"""


def badge_class(badge: str) -> str:
    b = (badge or "").upper()
    if "LIGHTNING" in b:
        return "lightning"
    if "STOCK" in b:
        return "restock"
    if "DROP" in b:
        return "drop"
    return ""


def price_html(p: dict, huge: bool = False) -> str:
    was = f'<span class="was">{money(p["was"])}</span>' if p.get("was") and p["was"] > p["price"] else ""
    return f'<span class="price{" huge" if huge else ""}">{money(p["price"])}</span>{was}'


def feed(w: World) -> str:
    tiles = []
    for p in w.feed():
        badge = f'<span class="badge {badge_class(p.get("badge"))}">{e(p["badge"])}</span>' if p.get("badge") else ""
        tiles.append(
            f'<a class="tile" href="{S}/p/{p["sku"]}" data-v="tile" data-title="{e(p["name"])}" '
            f'data-price="{p["price"]}" data-was="{p.get("was") or ""}" data-badge="{e(p.get("badge") or "")}">'
            f'<div class="pic">{p["emoji"]}</div><div>{badge}<div class="title">{e(p["name"])}</div>'
            f'{price_html(p)}</div></a>'
        )
    body = "<h1>Today's deals</h1>" + ("".join(tiles) or '<p class="muted">No deals right now.</p>')
    return store_page(w, "feed", "Deals", body, nav="nav_deals", reload=True)


def product(w: World, sku: str) -> str:
    p = w.products[sku]
    badge = f'<span class="badge {badge_class(p.get("badge"))}">{e(p["badge"])}</span>' if p.get("badge") else ""
    notes = []
    if not p.get("in_stock", True):
        notes.append('<p class="muted"><b>Out of stock</b></p>')
    if p.get("hold_minutes"):
        notes.append(f'<div class="notice">Lightning deal · add to cart to hold this price for {p["hold_minutes"]} minutes</div>')
    if "STOCK" in (p.get("badge") or "").upper():
        notes.append('<p><b>Back in stock.</b> Limited quantity.</p>')
    body = (f'<div class="pic big">{p["emoji"]}</div>{badge}'
            f'<h1 data-v="title" data-title="{e(p["name"])}">{e(p["name"])}</h1>'
            f'<div data-v="price" data-price="{p["price"]}" data-was="{p.get("was") or ""}">{price_html(p, True)}</div>'
            + "".join(notes) +
            '<p class="muted">Free shipping · Ships in 2 days</p>')
    bar = ""
    if p.get("in_stock", True) and p["live"]:
        bar = (f'<form method="post" action="{S}/cart/add"><input type="hidden" name="sku" value="{sku}">'
               '<button data-v="add_to_cart">Add to cart</button></form>')
    return store_page(w, "product", p["name"], body, bar,
                      attrs=f'data-title="{e(p["name"])}" data-price="{p["price"]}" data-was="{p.get("was") or ""}" data-badge="{e(p.get("badge") or "")}"')


def cart(w: World) -> str:
    if not w.cart:
        return store_page(w, "cart", "Cart", "<h1>Your cart</h1><p class='muted'>Your cart is empty.</p>", nav="nav_cart",
                          attrs='data-total="0"')
    rows, held = [], None
    for l in w.cart:
        rows.append(f'<div class="row" data-v="line" data-name="{e(l["name"])}" data-price="{l["price"]}">'
                    f'<b>{e(l["name"])}</b><span class="price">{money(l["price"])}</span></div>')
        held = held or l.get("held_until")
    total = sum(l["price"] for l in w.cart)
    hold = f'<div class="notice" data-v="hold" data-hold="{held}">Price held for you until {held}</div>' if held else ""
    body = ("<h1>Your cart</h1>" + "".join(rows) + hold +
            f'<div class="total"><span>Total</span><span data-v="total">{money(total)}</span></div>'
            f'<form method="post" action="{S}/cart/remove"><button class="link" data-v="remove">Remove from cart</button></form>')
    bar = f'<a class="btn" href="{S}/checkout" data-v="checkout">Checkout</a>'
    return store_page(w, "cart", "Cart", body, bar, nav="nav_cart",
                      attrs=f'data-total="{total}" data-hold="{held or ""}"')


def checkout(w: World) -> str:
    if not w.cart:
        return cart(w)
    base = sum(l["price"] for l in w.cart)
    rows = [f'<div class="row" data-v="line" data-name="{e(l["name"])}" data-price="{l["price"]}" data-checked="">'
            f'<b>{e(l["name"])}</b><span class="price">{money(l["price"])}</span></div>' for l in w.cart]
    total = base
    for a in w.addons():
        on = a.get("preticked")
        total += a["price"] if on else 0
        rows.append(
            f'<label class="row check" data-v="addon" data-name="{e(a["name"])}" data-price="{a["price"]}">'
            f'<input type="checkbox" form="place" name="addon" value="{a["id"]}" data-price="{a["price"]}" {"checked" if on else ""}>'
            f'<span style="flex:1"><b>{e(a["name"])}</b></span><span class="price">{money(a["price"])}</span></label>')
    rows.append('<div class="row"><span>Shipping</span><b>Free</b></div>')
    body = ("<h1>Checkout</h1>" + "".join(rows) +
            f'<div class="total"><span>Total</span><span data-v="total" id="total">{money(total)}</span></div>'
            '<p class="muted">Paying with Visa ending 4242</p>')
    bar = (f'<form method="post" action="{S}/checkout/place" id="place">'
           f'<button data-v="place_order" id="placebtn">Place order · {money(total)}</button></form>')
    script = f"""<script>
const BASE={base};
function fmt(x){{return '$'+(Number.isInteger(x)?x.toLocaleString():x.toFixed(2))}}
function upd(){{let t=BASE;document.querySelectorAll('input[name=addon]').forEach(c=>{{if(c.checked)t+=Number(c.dataset.price)}});
document.getElementById('total').textContent=fmt(t);document.getElementById('placebtn').textContent='Place order · '+fmt(t);document.body.dataset.total=t}}
document.querySelectorAll('input[name=addon]').forEach(c=>c.addEventListener('change',upd));
</script>"""
    return store_page(w, "checkout", "Checkout", body + script, bar, attrs=f'data-total="{total}"')


def confirmed(w: World, no: str) -> str:
    o = w.order(no)
    if not o:
        return orders(w)
    body = (f'<div class="ok">Order placed</div><h1>Order <span data-v="order_no" data-order="{o["no"]}">{o["no"]}</span></h1>'
            + "".join(f'<div class="row"><b>{e(l["name"])}</b><span>{money(l["price"])}</span></div>' for l in o["lines"])
            + "".join(f'<div class="row"><span>{e(a["name"])}</span><span>{money(a["price"])}</span></div>' for a in o["addons"])
            + f'<div class="total"><span>Paid</span><span data-v="total">{money(o["total"])}</span></div>')
    bar = f'<a class="btn" href="{S}" data-v="continue">Keep shopping</a>'
    return store_page(w, "order_confirmed", "Order placed", body, bar,
                      attrs=f'data-order="{o["no"]}" data-total="{o["total"]}"')


def orders(w: World) -> str:
    t = w.totals()
    tiles = []
    for o in reversed(w.orders):
        l = o["lines"][0]
        refund = f' · <b style="color:#0b7a50">{money(o["refunded"])} refunded</b>' if o["refunded"] else ""
        tiles.append(f'<a class="tile" href="{S}/orders/{o["no"]}" data-v="order" data-order="{o["no"]}" '
                     f'data-title="{e(l["name"])}" data-price="{o["total"]}">'
                     f'<div class="pic">{w.products[l["sku"]]["emoji"]}</div><div><div class="muted">{o["no"]} · {o["clock"]}</div>'
                     f'<div class="title">{e(l["name"])}</div><span class="price">{money(o["total"])}</span>{refund}</div></a>')
    summary = (f'<div class="row"><span>Spent today</span><b data-v="spent">{money(t["spent"])}</b></div>'
               f'<div class="row"><span>Refunded</span><b data-v="refunded">{money(t["refunded"])}</b></div>') if w.orders else ""
    body = "<h1>Order history</h1>" + summary + ("".join(tiles) or '<p class="muted">No orders yet.</p>')
    return store_page(w, "orders", "Orders", body, nav="nav_orders", reload=True,
                      attrs=f'data-spent="{t["spent"]}" data-refunded="{t["refunded"]}"')


def order_detail(w: World, no: str) -> str:
    o = w.order(no)
    if not o:
        return orders(w)
    l = o["lines"][0]
    body = (f'<h1>Order <span data-v="order_no" data-order="{o["no"]}">{o["no"]}</span></h1>'
            f'<p class="muted">Placed today at {o["clock"]}</p>'
            f'<div class="row" data-v="line" data-name="{e(l["name"])}" data-price="{l["price"]}"><b>{e(l["name"])}</b><span>{money(l["price"])}</span></div>'
            + "".join(f'<div class="row"><span>{e(a["name"])}</span><span>{money(a["price"])}</span></div>' for a in o["addons"])
            + f'<div class="total"><span>Paid</span><span>{money(o["total"])}</span></div>'
            + (f'<div class="ok">{money(o["refunded"])} refunded</div>' if o["refunded"] else "")
            + f'<p class="muted" data-v="policy">{e(w.catalog["policy_text"])}.</p>')
    bar = f'<a class="btn" href="{S}/chat/{o["no"]}" data-v="help">Get help with this order</a>'
    return store_page(w, "order_detail", f"Order {no}", body, bar, nav="nav_orders",
                      attrs=f'data-order="{o["no"]}" data-paid="{l["price"]}" data-policy="{e(w.catalog["policy_text"])}"')


def chat(w: World, no: str) -> str:
    msgs = w.chats.get(no, [])
    if not msgs:
        msgs = [{"from": "rep", "text": f"Hi! You're chatting with Brightcart support about order {no}. How can I help?"}]
    out, last_rep, refund = [], "", None
    for m in msgs:
        who = {"you": "You", "rep": "Brightcart support", "system": ""}[m["from"]]
        out.append(f'<div class="msg {m["from"]}" data-v="msg" data-from="{m["from"]}">'
                   + (f'<div class="who">{who}</div>' if who else "") + f'{e(m["text"])}</div>')
        if m["from"] == "rep":
            last_rep = m["text"]
        if m["from"] == "system" and "refunded" in m["text"]:
            refund = m["text"].split(" ")[0].lstrip("$").replace(",", "")
    body = f'<h1>Support · {no}</h1><div class="msgs">{"".join(out)}</div>'
    bar = (f'<form method="post" action="{S}/chat/{no}/send" class="chatbar" id="chatform">'
           '<textarea name="text" data-v="chat_input" placeholder="Type a message"></textarea>'
           '<button data-v="send">Send</button></form>')
    script = """<script>
addEventListener('DOMContentLoaded',()=>{
const ta=document.querySelector('textarea');
ta.addEventListener('keydown',ev=>{if(ev.key==='Enter'&&!ev.shiftKey){ev.preventDefault();if(ta.value.trim())document.getElementById('chatform').submit()}});
window.scrollTo(0,document.body.scrollHeight);});
</script>"""
    return store_page(w, "chat", "Support", body + script, bar, nav="nav_orders",
                      attrs=f'data-order="{no}" data-last-reply="{e(last_rep)}" data-refund="{refund or ""}"')


# ---------------------------------------------------------------- Maya, control, calibrate

APP_CSS = """
:root{--ink:#e8eef5;--muted:#8b98a8;--bg:#0b0f15;--card:#151c26;--line:#243041;--amber:#ffb547;--ok:#3ccf91;--no:#ff6b6b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:16px}
h1{font-size:24px;margin:0 0 4px}.muted{color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px;margin:12px 0}
button{font:700 20px system-ui,sans-serif;border:0;border-radius:14px;padding:16px;width:100%;cursor:pointer}
.primary{background:var(--amber);color:#1a1205}.ok{background:var(--ok);color:#06210f}.no{background:#2a3442;color:var(--ink)}
.pill{display:inline-block;padding:4px 10px;border-radius:999px;background:#2a1f3d;color:#d6c7ff;font-size:14px;font-weight:700}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.log div{padding:6px 0;border-bottom:1px solid var(--line);font-size:16px}.log b{color:var(--amber);font-weight:600;margin-right:6px}
.big{font-size:30px;font-weight:800}
"""


def _key_js(key_param: str) -> str:
    return f"const K=new URLSearchParams(location.search).get('k')||'';const H={{'Content-Type':'application/json','X-Hub-Key':K}};"


def maya(w: World) -> str:
    items = "".join(
        f'<div>• <b>{e(i["label"])}</b> <span class="muted">— '
        f'{"ask me first" if i["mode"] == "ask_first" else "pre-approved"}, up to {money(i["limit"])}'
        f'{", real deals only" if i["needs_real_deal"] else ""}</span></div>'
        for i in w.shopping["items"])
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maya · Lightning Rod</title><style>{APP_CSS}</style></head><body>
<h1>Lightning Rod</h1><div class="muted">Maya's agent · <span class="pill">Do Not Disturb</span> · <span id="clock"></span></div>
<div id="start" class="card"><div class="big">ER shift, 06:00–18:00</div><p class="muted">Your agent has its own phone and your list. It only asks you once, on your break.</p>
<button class="primary" id="go">Start my shift</button></div>
<div id="ask" class="card" hidden></div>
<div class="card"><b>My list</b> · budget {money(w.shopping["budget"])}<div style="margin-top:8px">{items}</div></div>
<div class="card"><b>Today</b><div class="grid" style="margin-top:8px"><div><div class="muted">Spent</div><div class="big" id="spent">$0</div></div>
<div><div class="muted">Refunded</div><div class="big" id="refunded">$0</div></div></div></div>
<div class="card log" id="log"></div>
<script>
{_key_js('k')}
const $=id=>document.getElementById(id);const fmt=x=>'$'+(Number.isInteger(x)?x.toLocaleString():x.toFixed(2));
$('go').onclick=async()=>{{await fetch('/api/agent/start',{{method:'POST',headers:H}});tick()}};
async function answer(id,d){{await fetch('/api/approvals/'+id+'/answer',{{method:'POST',headers:H,body:JSON.stringify({{decision:d}})}});tick()}}
async function tick(){{try{{const r=await fetch('/api/maya',{{headers:H,cache:'no-store'}});const s=await r.json();
$('clock').textContent=s.clock;$('start').hidden=s.agent.run;$('spent').textContent=fmt(s.totals.spent);$('refunded').textContent=fmt(s.totals.refunded);
const a=s.approval;const box=$('ask');
if(a){{box.hidden=false;box.innerHTML=`<div class="pill" style="background:#3d2a05;color:#ffd27a">Break · ${{s.break_clock}}</div>
<div class="big" style="margin:10px 0 4px">${{a.title}}</div><div>${{fmt(a.price)}} · your limit ${{fmt(a.limit)}}</div>
<p class="muted">${{a.reason||''}} Held until ${{a.hold_until||'?'}}.</p><div class="grid"><button class="ok" id="yes">Approve</button><button class="no" id="nah">Pass</button></div>`;
$('yes').onclick=()=>answer(a.id,'approve');$('nah').onclick=()=>answer(a.id,'decline')}}else box.hidden=true;
$('log').innerHTML='<b style="color:var(--ink)">What your agent did</b>'+s.log.slice().reverse().map(l=>`<div><b>${{l.clock}}</b>${{l.text}}</div>`).join('');
}}catch(_){{}}}}
tick();setInterval(tick,1000);
</script></body></html>"""


def control(w: World) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Control · Lightning Rod</title><style>{APP_CSS}</style></head><body>
<h1>Stage control</h1><div class="muted" id="sub"></div>
<div class="card"><div class="grid" id="beats"></div></div>
<div class="card grid"><button class="no" id="auto"></button><button class="no" id="reset">Reset world</button></div>
<div class="card" id="state"></div><div class="card log" id="log"></div>
<script>
{_key_js('k')}
const $=id=>document.getElementById(id);const fmt=x=>'$'+x;
async function post(p,b){{await fetch(p,{{method:'POST',headers:H,body:JSON.stringify(b||{{}})}});tick()}}
$('reset').onclick=()=>{{if(confirm('Reset the whole world?'))post('/api/control/reset')}};
async function tick(){{try{{const r=await fetch('/api/world',{{headers:H,cache:'no-store'}});const s=await r.json();
$('sub').textContent=`Story clock ${{s.clock}} · agent: ${{s.agent.run?(s.agent.end?'ending':'running'):'not started'}} · ${{s.agent.status}}`;
$('beats').innerHTML=s.beats.map(b=>`<button class="${{s.fired.includes(b.id)?'no':(b.id===s.next?'primary':'no')}}" data-b="${{b.id}}">${{s.fired.includes(b.id)?'✓ ':''}}${{b.label}}</button>`).join('');
document.querySelectorAll('[data-b]').forEach(x=>x.onclick=()=>post('/api/control/fire/'+x.dataset.b));
$('auto').textContent='Solo auto mode: '+(s.auto?'ON':'off');$('auto').className=s.auto?'ok':'no';$('auto').onclick=()=>post('/api/control/auto',{{on:!s.auto}});
const a=s.approval;$('state').innerHTML=`Waiting on agent: <b>${{s.awaiting||'—'}}</b><br>Approval: <b>${{a?a.title+' (pending)':'none pending'}}</b><br>Spent ${{fmt(s.totals.spent)}} · refunded ${{fmt(s.totals.refunded)}}`;
$('log').innerHTML=s.log.slice().reverse().map(l=>`<div><b>${{l.clock}}</b>[${{l.kind}}] ${{l.text}}</div>`).join('');
}}catch(_){{}}}}
tick();setInterval(tick,1000);
</script></body></html>"""


def calibrate(w: World) -> str:
    targets = []
    n = 0
    for row in range(5):
        for col in range(3):
            n += 1
            x, y = 16.6 + col * 33.3, 14 + row * 17
            targets.append(f'<div class="t" data-v="target" data-n="{n}" style="left:{x}%;top:{y}%">{n}</div>')
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calibrate</title><style>
html,body{{margin:0;height:100%;background:#fff;font-family:system-ui,sans-serif;overflow:hidden}}
.t{{position:fixed;width:64px;height:64px;margin:-32px 0 0 -32px;border-radius:50%;background:#ff7a3d;color:#fff;display:grid;place-items:center;font:800 26px system-ui}}
.t.hit{{background:#0b7a50}}
textarea{{position:fixed;left:5%;right:5%;bottom:3%;height:7%;font:18px system-ui;border:2px solid #ccc;border-radius:12px}}
h1{{position:fixed;top:1%;left:0;right:0;text-align:center;font-size:22px;margin:0}}
</style></head><body data-screen="calibrate"><h1>Calibration</h1>{''.join(targets)}
<textarea data-v="chat_input" placeholder="Type here"></textarea>
<script>
const send=b=>fetch('/api/calibration/hit',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(b)}});
addEventListener('pointerdown',ev=>{{const t=ev.target.closest('.t');if(t)t.classList.add('hit');
send({{n:t?Number(t.dataset.n):0,x:ev.clientX,y:ev.clientY,w:innerWidth,h:innerHeight}})}});
document.querySelector('textarea').addEventListener('input',ev=>fetch('/api/calibration/text',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{text:ev.target.value}})}}));
</script></body></html>"""
