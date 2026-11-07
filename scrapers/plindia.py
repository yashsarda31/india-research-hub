"""PL Capital (Prabhudas Lilladher) research -> data/raw/plindia.jsonl
Source: https://www.plindia.com/pl-research/ (paginated, 30 cards/page, newest first);
each card links to a detail page that has the summary, datePublished (JSON-LD) and a direct PDF link.
"""
import os, re, sys, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
from common import session, make_record, Writer, polite, MIN_DATE, clean

SRC = "plindia"
BASE = "https://www.plindia.com/pl-research/"
RATINGS = ["BUY", "SELL", "HOLD", "ACCUMULATE", "REDUCE", "ADD", "NEUTRAL", "UNDERPERFORM", "OUTPERFORM"]


def parse_title(t):
    t = html.unescape(t).replace("\u2013", "-").replace("\u2014", "-")
    parts = [p.strip() for p in re.split(r"\s+-\s+", t)]
    company = rtype = rating = None
    m = re.match(r"(.+?)\s*\(([A-Z0-9&\-\.]+) IN\)", parts[0])
    if m:
        company = m.group(1).strip()
        if len(parts) > 1:
            rtype = parts[1]
        last = re.sub(r"[‘’'\"]", "", parts[-1]).upper()
        for r in RATINGS:
            if re.search(r"\b" + r + r"\b", last):
                rating = r
                break
    else:
        company = None
        if len(parts) > 1:
            rtype = parts[0]
    return company, rtype, rating


def main():
    s = session()
    w = Writer(SRC)
    import json
    seen_urls = set()
    done = set()
    if os.path.exists(w.path):
        for ln in open(w.path, encoding='utf8'):
            try:
                done.add(json.loads(ln)['page_url'])
            except Exception:
                pass
    page = int(os.environ.get('PL_START', '1'))
    end_page = int(os.environ.get('PL_END', '9999'))
    stop = False
    while not stop and page <= end_page:
        url = BASE if page == 1 else f"{BASE}page/{page}/"
        r = s.get(url, timeout=40)
        if r.status_code != 200:
            break
        b = BeautifulSoup(r.text, "lxml")
        cards = [a for a in b.select("a.report-card-link")]
        if not cards:
            break
        old_in_page = 0
        for a in cards:
            href = a["href"]
            if href in seen_urls:
                continue
            seen_urls.add(href)
            if href in done:
                continue
            polite(0.5)
            try:
                d = s.get(href, timeout=40)
            except Exception as e:
                print("ERR", href, e); continue
            if d.status_code != 200:
                continue
            m = re.search(r'datePublished":"([^"]+)', d.text)
            date = m.group(1)[:10] if m else None
            db = BeautifulSoup(d.text, "lxml")
            btn = db.select_one(".research-cta a[href]")
            pdf = btn["href"].replace(" ", "%20") if btn and ".pdf" in btn["href"].lower() else None
            if pdf and pdf.startswith("http://"):
                pdf = "https://" + pdf[7:]
            content = db.select_one(".research-content")
            summary = clean(content.get_text(" ", strip=True)) if content else None
            title = clean(html.unescape(a.select_one("h3").get_text(" ", strip=True)))
            company, rtype, rating = parse_title(title)
            tab = db.select_one("article")
            sector = None
            if tab:
                for c in tab.get("class", []):
                    if c.startswith("research_desk_tab-"):
                        sector = None
                        if not rtype:
                            rtype = c.split("-", 1)[1].title()
            if date and date < MIN_DATE:
                old_in_page += 1
            rec = make_record(SRC, broker="PL Capital", company=company, title=title, date=date,
                              report_type=rtype, rating=rating, summary=summary, pdf_url=pdf,
                              page_url=href, sector=sector)
            w.add(rec); w.f.flush()
        print(f"page {page}: {len(cards)} cards, old={old_in_page}, added={w.added}", flush=True)
        if old_in_page >= len(cards) - 2 and not any(c['href'] in done for c in cards):
            stop = True
        page += 1
        polite(0.5)
    w.close()


if __name__ == "__main__":
    main()
