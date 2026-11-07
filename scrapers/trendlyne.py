"""Trendlyne research-report aggregator (all brokers).

Walks https://trendlyne.com/research-reports/all/?page=N newest-first and stops
once a whole page is older than MIN_DATE. PDFs on Trendlyne need a (free) login,
so pdf_url stays None; page_url is the public post page, and the site builder
derives the logged-in PDF link (get-document/post/pdf/<post id>/) from it.

    python scrapers/trendlyne.py [max_pages]
"""
import re
import sys
import time

from bs4 import BeautifulSoup

from common import MIN_DATE, Writer, make_record, norm_date, session

BASE = "https://trendlyne.com/research-reports/all/"
RATING_WORDS = {"buy", "sell", "hold", "accumulate", "add", "reduce", "neutral",
                "outperform", "underperform", "strong buy", "sell on rise",
                "buy on dips", "not rated", "trading buy", "positive", "negative"}


def first_num(t):
    m = re.search(r"-?\d[\d,]*\.?\d*", t or "")
    return m.group(0).replace(",", "") if m else None


def parse_rows(html):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []
    out = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 11:
            continue
        date = norm_date(tds[1].get("data-sort") or tds[1].get_text(strip=True))
        a = tds[2].find("a", href=True)
        company = a.get_text(strip=True) if a else None
        symbol = None
        if a:
            m = re.search(r"/research-reports/stock/\d+/([^/]+)/", a["href"])
            symbol = m.group(1) if m else None
        is_equity = bool(tr.find("script", string=re.compile(r"trendlyne\.com/equity/")))
        b = tds[3].find("a", class_="broker-link")
        broker = b.get_text(strip=True) if b else tds[3].get_text(" ", strip=True)
        typ = tds[8].get_text(" ", strip=True)
        rating = typ if typ.lower() in RATING_WORDS else None
        report_type = None if rating else typ
        hid = tds[-1]
        h = hid.find("h6")
        title = h.get_text(" ", strip=True) if h else None
        summ = hid.find("div", class_="m-b-1")
        summary = summ.get_text(" ", strip=True) if summ else None
        post = hid.find("a", class_="copy-post-link")
        page_url = post.get("data-href") if post else None
        if not page_url:
            p = tds[9].find("a", href=re.compile(r"/posts/\d+"))
            page_url = p["href"] if p else None
        out.append(make_record(
            "trendlyne",
            broker=broker,
            company=company if is_equity else None,
            symbol=symbol if is_equity else None,
            title=title or (f"{company} – {typ}" if company else typ),
            date=date,
            report_type=report_type or ("Stock Report" if is_equity else None),
            rating=rating,
            target=first_num(tds[5].get_text(" ", strip=True)),
            price_at_reco=first_num(tds[6].get_text(" ", strip=True)),
            summary=summary,
            pdf_url=None,
            page_url=page_url,
            sector=None if is_equity else company,  # e.g. "Market Movement", sector notes
        ))
    return out


def main():
    max_pages = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    s = session()
    w = Writer("trendlyne")
    old_pages = 0
    try:
        for page in range(1, max_pages + 1):
            url = BASE if page == 1 else f"{BASE}?page={page}"
            for attempt in range(4):
                try:
                    r = s.get(url, timeout=40)
                    if r.status_code == 200:
                        break
                    print(f"page {page}: HTTP {r.status_code}, retry", flush=True)
                except Exception as e:  # network hiccup
                    print(f"page {page}: {e!s:.80}, retry", flush=True)
                time.sleep(5 * (attempt + 1))
            else:
                print(f"page {page}: giving up", flush=True)
                continue
            recs = parse_rows(r.text)
            if not recs:
                print(f"page {page}: no rows, stopping", flush=True)
                break
            for rec in recs:
                w.add(rec)
            dates = [x["date"] for x in recs if x["date"]]
            if dates and max(dates) < MIN_DATE:
                old_pages += 1
                if old_pages >= 2:  # two full pages past the cutoff -> done
                    print(f"page {page}: past {MIN_DATE}, stopping", flush=True)
                    break
            else:
                old_pages = 0
            if page % 25 == 0:
                print(f"page {page}: {min(dates) if dates else '?'}  added={w.added}", flush=True)
                w.f.flush()
            time.sleep(0.7)
    finally:
        w.close()


if __name__ == "__main__":
    main()
