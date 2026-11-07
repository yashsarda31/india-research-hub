"""Axis Direct (Axis Securities) research -> data/raw/axisdirect.jsonl
Listing: https://simplehai.axisdirect.in/app/index.php/insights/reports/fundamental (and /sector). The page is
server-rendered 9 cards at a time; further cards come from POST .../insights/reports/search with the form fields
(dbmodel, offsetVal, assignCount, ...). Each card has a public PDF at
.../insights/reports/downloadReport/file/<name>.pdf/type/<fundamental|sector> (no login; returns application/pdf).
Newest first -> stop once a page is entirely pre-2026.
"""
import os, re, sys, html
from urllib.parse import unquote_plus
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
from common import session, make_record, Writer, polite, MIN_DATE, clean, norm_date

SRC = "axisdirect"
BASE = "https://simplehai.axisdirect.in"
SECTIONS = ["fundamental", "sector"]
RATING = re.compile(r"\b(BUY|SELL|HOLD|REDUCE|ACCUMULATE|ADD|NEUTRAL|OUTPERFORM|UNDERPERFORM|OVERWEIGHT|UNDERWEIGHT)\b")
TARGET = re.compile(r"(?:\bTP\b|\bTarget(?: Price)?\b|\bPT\b)[^0-9]{0,40}?(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d+)?)", re.I)
CMP = re.compile(r"\b(?:CMP|current market price)[^0-9]{0,20}([\d,]+(?:\.\d+)?)", re.I)


def parse_cards(htm, typ, w):
    b = BeautifulSoup(htm, "lxml")
    cards = b.select("li.search_ids")
    old = 0
    for li in cards:
        h = li.select_one("h5.report-proname")
        title = clean(h.get("title") or h.get_text(" ", strip=True)) if h else None
        dt = li.select_one("p.reports-time")
        date = norm_date(clean(dt.get_text(" ", strip=True))) if dt else None
        if date and date < MIN_DATE:
            old += 1
        a = li.select_one("a.download-report-btn")
        pdf = None
        if a and a.get("href"):
            pdf = BASE + a["href"].replace(" ", "+")
        names = []
        for x in li.select(".report-name-fly a"):
            n = clean(x.get_text(" ", strip=True))
            if n and n not in names:
                names.append(n)
        sm = li.select_one(".reports-video .reports-video")
        summary = clean(sm.get_text(" ", strip=True)) if sm else None
        rtype = None
        if title and ":" in title:
            rtype = title.split(":", 1)[0].strip()
        elif pdf:
            fn = unquote_plus(pdf.split("/file/")[1].split("/type/")[0])
            m = re.search(r"(Result Update|Initiating Coverage|Company Update|Event Update|Flash Note|Result Preview|Visit Note)", fn, re.I)
            rtype = m.group(1) if m else None
        blob = (title or "") + " " + (summary or "")
        mr = RATING.search(blob)
        mt = TARGET.search(summary or "")
        mc = CMP.search(summary or "")
        company = names[0] if len(names) == 1 else None
        w.add(make_record(SRC, broker="Axis Securities", company=company, title=title, date=date,
                          report_type=rtype, rating=mr.group(1) if mr else None,
                          target=mt.group(1) if mt else None, price_at_reco=mc.group(1) if mc else None,
                          summary=summary, pdf_url=pdf,
                          page_url=f"{BASE}/app/index.php/insights/reports/{typ}",
                          sector=None))
    return len(cards), old, [li.get('id') for li in cards]


def main():
    s = session()
    w = Writer(SRC)
    for typ in SECTIONS:
        page_url = f"{BASE}/app/index.php/insights/reports/{typ}"
        r = s.get(page_url, timeout=60)
        b = BeautifulSoup(r.text, "lxml")
        dbmodel = (b.select_one("input[name=dbmodel]") or {}).get("value")
        total = (b.select_one("input[name=assignCount]") or {}).get("value", "0")
        n, old, ids = parse_cards(r.text, typ, w)
        seen_ids = list(ids)
        print(typ, dbmodel, "total", total, "first page", n, "old", old, flush=True)
        offset = 0
        while old < n and n > 0:
            offset += 9
            polite(0.7)
            data = {"searchStr": "", "categoryId": "", "date": "all", "format": "all", "dbmodel": dbmodel,
                    "offsetVal": str(offset), "sortVal": "", "assignCount": total,
                    "ids": "".join(i + "," for i in seen_ids)}
            r = s.post(f"{BASE}/app/index.php/insights/reports/search", data=data,
                       headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url}, timeout=60)
            if "No Data" in r.text and "search_ids" not in r.text:
                break
            n, old, ids = parse_cards(r.text, typ, w)
            seen_ids += ids
            print(typ, "offset", offset, "cards", n, "old", old, "added", w.added, flush=True)
            if n == 0:
                break
    w.close()


if __name__ == "__main__":
    main()
