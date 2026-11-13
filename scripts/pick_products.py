"""9:30: look up today's real prices with Tavily and suggest the store's beat prices.

  python scripts/pick_products.py                 (prints what it finds)
  python scripts/pick_products.py --write         (also saves data/price_snapshot.json, the offline fallback)
  python scripts/pick_products.py --title headphones="Bose QuietComfort Ultra Headphones"   (try another product)

Then edit data/catalog.json by hand: product names, and the prices in each beat.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import config  # noqa: E402
from agent.pricecheck import extract_prices  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--title", action="append", default=[], help='item=product title, e.g. tv="LG 65 inch C4 OLED"')
    a = ap.parse_args()
    if not config.TAVILY_API_KEY:
        sys.exit("Set TAVILY_API_KEY in .env first.")
    from tavily import TavilyClient
    client = TavilyClient(api_key=config.TAVILY_API_KEY)

    snap_path = config.DATA / "price_snapshot.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    shopping = json.loads((config.DATA / "shopping_list.json").read_text(encoding="utf-8"))
    titles = {k: v["title"] for k, v in snap["items"].items()}
    for t in a.title:
        k, _, v = t.partition("=")
        titles[k.strip()] = v.strip().strip('"')
    limits = {i["key"]: i["limit"] for i in shopping["items"]}

    out = {"sample": False, "taken": time.strftime("%Y-%m-%d %H:%M"), "items": {}}
    for key, title in titles.items():
        t0 = time.time()
        res = client.search(query=f"{title} price", search_depth="basic", max_results=8, include_domains=config.RETAILERS)
        prices = extract_prices(res.get("results", []), None)
        med = statistics.median(p["price"] for p in prices) if prices else None
        print(f"\n{key}: {title}   ({time.time() - t0:.1f}s)")
        for p in prices:
            print(f"   {p['store']:<12} ${p['price']:,.2f}")
        if med is None:
            print("   no prices found: try a more specific title with --title")
            continue
        print(f"   median ${med:,.2f}")
        if key == "tv":
            print(f"   suggested fake-deal beat price: ${round(med)} (same as everyone else; the agent should skip it)")
        elif key == "headphones":
            hi = min(limits.get(key, 300) - 1, round(med * 0.82))
            print(f"   suggested lightning price: ${hi} (real low, under the ${limits.get(key)} limit), drop to ${hi - 30}")
        elif key == "console":
            print(f"   pre-approved limit is ${limits.get(key)}; set the restock price at or under it")
        out["items"][key] = {"title": title, "prices": prices}
    if a.write:
        snap_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nSaved {snap_path}")


if __name__ == "__main__":
    main()
