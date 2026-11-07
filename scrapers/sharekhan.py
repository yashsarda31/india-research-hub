"""Mirae Asset Sharekhan fundamental research -> data/raw/sharekhan.jsonl
Listing: https://research.sharekhan.com/research-reports/fundamental/stock-updates (server-rendered, ~730 rows,
one 8 MB page). Public visitors get title/date/analyst/one-line synopsis (with rating + target usually) and the
NSE code (data-recombtnsskicode) but the PDF links are masked ("XXXX") behind a mobile-OTP login, so
pdf_url=None for all rows and page_url = the listing page.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
from common import session, make_record, Writer, clean

SRC = "sharekhan"
URL = "https://research.sharekhan.com/research-reports/fundamental/stock-updates"
RT = {"Stock Update": "Company Update", "Earnings Preview/Review": "Result Update", "New Stock Idea": "Initiating Coverage",
      "Sector Updates": "Sector Update", "Viewpoint": "Market Viewpoint", "Market Outlook": "Market Outlook",
      "Diwali Picks": "Strategy", "Techno Funda - Vantage": "Stock Picks", "ValueGuide - Equity": "Stock Picks",
      "IPO Flash": "IPO Note", "Arc - Equity": "Strategy", "Budget Preview/Review": "Strategy"}
RATING = re.compile(r"\b(buy|sell|hold|reduce|accumulate|add|neutral|outperform|underperform|positive|negative)\b", re.I)
TARGET = re.compile(r"(?:price target|PT|target price|TP|target)[^0-9]{0,40}?(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d+)?)", re.I)
CMP = re.compile(r"CMP[^0-9]{0,15}([\d,]+(?:\.\d+)?)", re.I)


def main():
    s = session()
    import time
    html = None
    if os.environ.get("SHAREKHAN_HTML"):  # optional saved copy of the listing page
        html = open(os.environ["SHAREKHAN_HTML"], encoding="utf8").read()
    else:
        for _ in range(6):  # site intermittently 503s / rate-limits
            r = s.get(URL, timeout=120)
            if r.status_code == 200 and "main-report-row" in r.text:
                html = r.text
                break
            print("retry", r.status_code); time.sleep(15)
    if not html:
        sys.exit("sharekhan: listing unavailable (503)")
    b = BeautifulSoup(html, "lxml")
    w = Writer(SRC)
    for row in b.select("tr.main-report-row"):
        name = row.get("data-report-name")
        d = (row.get("data-date") or "")[:10]  # dd-mm-yyyy
        m = re.match(r"(\d\d)-(\d\d)-(\d{4})", d)
        date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
        title = clean((row.select_one(".report-title") or {}).get_text(" ", strip=True) if row.select_one(".report-title") else None)
        desc = clean(row.select_one(".report-description").get_text(" ", strip=True)) if row.select_one(".report-description") else None
        a = row.select_one("a[data-recombtnsskicode]")
        sym = clean(a.get("data-recombtnsskicode")) if a else None
        sector = clean(row.select_one("#td_sector").get_text(" ", strip=True)) if row.select_one("#td_sector") else None
        rating = tgt = cmp_ = None
        if desc:
            mr = RATING.search(desc)
            rating = mr.group(1) if mr else None
            mt = TARGET.search(desc)
            tgt = mt.group(1) if mt else None
            mc = CMP.search(desc)
            cmp_ = mc.group(1) if mc else None
        if not sym:
            rating = rating if name in ("New Stock Idea",) else rating
        w.add(make_record(SRC, broker="Mirae Asset Sharekhan", company=None, symbol=sym or None,
                          title=title, date=date, report_type=RT.get(name, name), rating=rating,
                          target=tgt, price_at_reco=cmp_, summary=desc, pdf_url=None,
                          page_url=URL, sector=sector))
    w.close()


if __name__ == "__main__":
    main()
