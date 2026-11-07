"""Moneycontrol broker-research stock ideas API (direct PDFs on images.moneycontrol.com)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

API = "https://api.moneycontrol.com/mcapi/v1/broker-research/stock-ideas"
RATING = {"B": "BUY", "S": "SELL", "N": "HOLD", "H": "HOLD"}

def main():
    s = session(); w = Writer("moneycontrol")
    start, limit, empty = 0, 50, 0
    while True:
        try:
            r = s.get(API, params={"start": start, "limit": limit, "deviceType": "W"}, timeout=40)
            rows = r.json().get("data") or []
        except Exception as e:
            print("err", start, e); empty += 1
            if empty > 3: break
            polite(3); continue
        if not rows or not isinstance(rows, list):
            break
        old = 0
        for x in rows:
            d = norm_date(x.get("entry_date") or x.get("target_price_date"))
            if not d or d < MIN_DATE:
                old += 1; continue
            stk = x.get("stkname")
            sector = (x.get("stk_url") or "").split("/")[0] or None
            w.add(make_record("moneycontrol", broker=x.get("organization"), company=stk,
                title=x.get("heading"), date=d, report_type="Broker Recommendation",
                rating=x.get("recommend_flag"), target=x.get("target_price"),
                price_at_reco=x.get("recommended_price"), pdf_url=x.get("attachment") or None,
                page_url="https://www.moneycontrol.com/markets/stock-ideas/", sector=sector))
        print(start, len(rows), "old", old, "added", w.added, flush=True)
        if old == len(rows):
            break
        start += limit; polite(0.5)
    w.close()

if __name__ == "__main__":
    main()
