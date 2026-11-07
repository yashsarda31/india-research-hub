"""ICICI Direct / ICICI Securities retail research -> data/raw/icicidirect.jsonl

Two public things exist (everything else on /research is behind 'Unlock'):
 1. "Investing ideas" cards on /research/equity -> direct PDFs on
    mailcontent.icicidirect.com/mailcontent/idirect_<co>_<qXfyYY>.pdf with CMP/target
    (card has no date; publication date is read from the PDF's first page with pypdf).
 2. ICICIdirect Research blog posts (/research/equity/blog/<slug>), listed in
    research-equity-article-sitemap.xml. These are HTML articles (no PDF); title often
    carries "CMP / Target / Buy" for 'Hidden Gem' stock picks. datePublished is read
    from the page JSON-LD. pdf_url=None, page_url=article.
"""
import io
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup  # noqa: E402
from common import MIN_DATE, Writer, make_record, norm_date, session, polite, clean  # noqa: E402

SRC = "icicidirect"
BROKER = "ICICI Securities"
BASE = "https://www.icicidirect.com"
TIME_BUDGET = 22 * 60  # seconds for the blog crawl
T0 = time.time()
s = session()


def get(url, **kw):
    for i in range(3):
        try:
            r = s.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (404, 410):
                return None
        except Exception as e:  # noqa: BLE001
            print("  retry", url[-60:], str(e)[:60])
        polite(1.5)
    return None


MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def pdf_date(url):
    """Read the report date from the first page text of a (small) PDF."""
    try:
        from pypdf import PdfReader
        r = get(url)
        if not r or not r.content.startswith(b"%PDF"):
            return None
        rd = PdfReader(io.BytesIO(r.content))
        txt = (rd.pages[0].extract_text() or "")[:3000]
        m = re.search(r"\b(\d{1,2})[\s-]+(%s)[a-z]*[\s,.-]+(20\d\d)" % MONTHS, txt, re.I)
        if m:
            return norm_date("%s %s %s" % (m.group(1), m.group(2)[:3], m.group(3)))
        info = rd.metadata
        cd = getattr(info, "creation_date", None)
        if cd:
            return cd.strftime("%Y-%m-%d")
    except Exception as e:  # noqa: BLE001
        print("  pdf date fail", url[-40:], str(e)[:60])
    return None


def investing_ideas(w):
    url = BASE + "/research/equity"
    r = get(url)
    if not r:
        print("equity page failed")
        return
    b = BeautifulSoup(r.text, "lxml")
    n = 0
    for a in b.find_all("a", href=True):
        if not re.match(r"\s*View Report", a.get_text(" ", strip=True)):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = "https://mailcontent.icicidirect.com/mailcontent/" + href.lstrip("/")
        card = a
        for _ in range(6):
            card = card.parent
            if card is None or "Target Price" in card.get_text(" ", strip=True):
                break
        if card is None:
            continue
        t = card.get_text(" ", strip=True)
        nm = card.find(["h3", "h2"])
        a2 = nm.find("a") if nm else None
        company = (a2.get("title") if a2 and a2.get("title") else (nm.get_text(" ", strip=True) if nm else None))
        sym = None
        buy = card.find("a", href=re.compile(r"cashbuy/"))
        if buy:
            sym = None  # ICICI code (e.g. KRIINS) is not the NSE ticker; leave for merge step
        cmp_ = re.search(r"CMP\s*([\d,\.]+)", t)
        tgt = re.search(r"Target Price\s*([\d,\.]+)", t)
        rating = re.search(r"View Report\s*(Buy|Sell|Hold|Add|Reduce|Accumulate)", t, re.I)
        if not href.lower().endswith(".pdf") or "idirect_" not in href:
            continue  # e.g. the AMFI market-cap pdf mislinked on the page
        date = pdf_date(href)
        polite()
        fn = href.rsplit("/", 1)[-1]
        qm = re.search(r"_(q\dfy\d\d)", fn, re.I)
        w.add(make_record(
            SRC, broker=BROKER, company=company, symbol=sym,
            title="%s - %s Result Update / Investing Idea" % (company, qm.group(1).upper() if qm else "Latest"),
            date=date, report_type="Result Update", rating=rating.group(1) if rating else "BUY",
            target=tgt.group(1) if tgt else None, price_at_reco=cmp_.group(1) if cmp_ else None,
            pdf_url=href, page_url=url))
        n += 1
    print("investing ideas cards:", n)


STOCKY = re.compile(r"hidden-gem|target|result|q[1-4]fy|earnings|buy|initiat|stock|ltd|bank|-cmp-", re.I)


def blogs(w):
    r = get(BASE + "/research-equity-article-sitemap.xml")
    if not r:
        print("sitemap failed")
        return
    urls = re.findall(r"<loc>(https://www\.icicidirect\.com/research/equity/blog/[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", r.text)
    urls = [(u, d) for u, d in urls if d >= MIN_DATE]
    urls.sort(key=lambda x: (0 if STOCKY.search(x[0]) else 1, x[1]), reverse=False)
    print("blog urls with lastmod >= 2026:", len(urls))
    done = 0
    for u, lm in urls:
        if time.time() - T0 > TIME_BUDGET:
            print("time budget hit after", done)
            break
        r = get(u)
        polite(0.5)
        if not r:
            continue
        done += 1
        t = r.text
        m = re.search(r'"datePublished":\s*"([^"]+)"', t)
        date = norm_date(m.group(1)) if m else None
        b = BeautifulSoup(t, "lxml")
        h1 = b.find("h1")
        title = clean(h1.get_text(" ", strip=True)) if h1 else None
        if not title:
            continue
        lines = [x.strip() for x in b.get_text("\n", strip=True).split("\n")]
        summ = None
        try:
            i = lines.index("DISCLAIMER")
            body = []
            for x in lines[i + 1:]:
                if x.startswith("Trending Blogs") or x.startswith("Quick Links"):
                    break
                body.append(x)
            summ = " ".join(body)
        except ValueError:
            pass
        rating = target = cmp_ = company = None
        mm = re.search(r"Target\s*[-–:]?\s*₹?\s*([\d,\.]+)", title, re.I)
        if mm:
            target = mm.group(1)
        mm = re.search(r"CMP\s*[-–:]?\s*₹?\s*([\d,\.]+)", title, re.I)
        if mm:
            cmp_ = mm.group(1)
        mm = re.search(r",\s*(Buy|Sell|Hold|Add|Reduce|Accumulate)\s*\)", title, re.I)
        if mm:
            rating = mm.group(1)
        mm = re.match(r"Hidden Gem\s*[:\-–]\s*(.+?)(?:\s*\(|$)", title, re.I)
        if mm:
            company = mm.group(1).strip()
        rtype = "Hidden Gem (stock pick)" if company else "Research Blog"
        w.add(make_record(
            SRC, broker=BROKER, company=company, symbol=None, title=title, date=date,
            report_type=rtype, rating=rating, target=target, price_at_reco=cmp_,
            summary=summ, pdf_url=None, page_url=u))
        if done % 100 == 0:
            w.f.flush()
            print("  blogs fetched", done, "added", w.added)
    print("blogs fetched", done)


def main():
    w = Writer(SRC)
    investing_ideas(w)
    blogs(w)
    w.close()


if __name__ == "__main__":
    main()
