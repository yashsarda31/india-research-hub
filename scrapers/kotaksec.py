"""Kotak Securities (Kotak Neo) fundamental/derivative research -> data/raw/kotaksec.jsonl

kotaksecurities.com redirects to kotakneo.com. Public PDFs live at
https://www.kotakneo.com/uploads/<name>_<hash>.pdf (plain GET works, no login;
a Referer of the listing page is sent anyway). Pages are Next.js server-rendered
so the listing HTML already contains the dated links.
Sections scraped: weekly-top-picks, monthly-top-picks, opportune (one-pagers),
rating-monitor, stock-recommendation-reports (daily), derivative-research-report.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup  # noqa: E402
from common import Writer, make_record, norm_date, session, polite, clean  # noqa: E402

SRC = "kotaksec"
BROKER = "Kotak Securities"
BASE = "https://www.kotakneo.com"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

s = session()
_lm_cache = {}


def get(url, **kw):
    for i in range(3):
        try:
            r = s.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
        except Exception as e:  # noqa: BLE001
            print("  retry", url, str(e)[:80])
        polite(1.5)
    return None


def date_from_name(name):
    """dd_Mon_yyyy / dd_mm_yyyy found in a filename."""
    n = re.sub(r"%20", "_", name)
    m = re.search(r"(\d{1,2})[_\- ]?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[_\- ]?(20\d\d)", n, re.I)
    if m:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"_(\d{1,2})_(\d{2})_(20\d\d)_", n)
    if m:
        return "%s-%s-%02d" % (m.group(3), m.group(2), int(m.group(1)))
    return None


def last_modified(url):
    """Upload date from the Last-Modified header, without downloading the body."""
    if url in _lm_cache:
        return _lm_cache[url]
    d = None
    try:
        r = s.get(url, stream=True, timeout=60, headers={"Referer": BASE + "/fundamental-research-report/"})
        lm = r.headers.get("last-modified")
        if lm:
            from email.utils import parsedate_to_datetime
            d = parsedate_to_datetime(lm).strftime("%Y-%m-%d")
        try:
            r.close()
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        print("  LM fail", url[-50:], str(e)[:60])
    polite(0.5)
    _lm_cache[url] = d
    return d


def soup(url):
    r = get(url)
    return BeautifulSoup(r.text, "lxml") if r else None


def climb(a, needle, maxup=6):
    node = a
    for _ in range(maxup):
        node = node.parent
        if node is None:
            return None
        if needle in node.get_text(" ", strip=True):
            return node
    return None


def split_name(txt):
    m = re.match(r"(.*?)\s*\(([^)]+)\)\s*$", txt.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else (txt.strip(), None)


def rtype_from_name(fn):
    f = fn.lower()
    if "rating_monitor" in f:
        return "Rating Monitor"
    if "result" in f:
        return "Result Update"
    if "one_pager" in f or "one-pager" in f:
        return "Company Update"
    if "pick_of_the_week" in f:
        return "Pick of the Week"
    return "Company Report"


def list_picks(w, path, rtype):
    """weekly / monthly top picks pages."""
    url = f"{BASE}/fundamental-research-report/{path}/"
    b = soup(url)
    if not b:
        print("fail", url)
        return
    cur_month_date = None
    n = 0
    for el in b.find_all(True):
        own = el.find(string=True, recursive=False)
        if own:
            m = re.search(r"Top Stock Picks for (\w+) (\d{4})", str(own))
            if m and m.group(1)[:3].lower() in MONTHS:
                cur_month_date = "%s-%02d-01" % (m.group(2), MONTHS[m.group(1)[:3].lower()])
        if el.name == "a" and re.match(r"research report", el.get_text(" ", strip=True), re.I):
            href = el.get("href") or ""
            if not href.lower().endswith(".pdf"):
                continue
            card = climb(el, "Reco. Price")
            if not card:
                continue
            for _ in range(5):
                t = card.get_text(" ", strip=True)
                if t.count("Reco. Price") > 1:
                    break
                if t.split("Reco. Price")[0].strip() and (rtype != "Pick of the Week" or "Call Date" in t):
                    break
                card = card.parent
            t = card.get_text(" ", strip=True)
            # strip the 'Research report' word and trailing rating
            nm = re.match(r"(.*?)\s*(?:Call Date:|Reco\. Price)", t)
            company, code = split_name(nm.group(1)) if nm else (None, None)
            dm = re.search(r"Call Date:\s*(\d{1,2})\w*\s+(\w+),?\s+(\d{4})", t)
            if dm:
                date = norm_date("%s %s %s" % (dm.group(1), dm.group(2)[:3], dm.group(3)))
            else:
                date = cur_month_date
            pm = re.search(r"Reco\. Price\s*₹\s*([\d,\.]+)", t)
            tm = re.search(r"Target\s*₹\s*([\d,\.]+)", t)
            rm = re.search(r"Research report\s*(Buy|Add|Reduce|Sell|Hold|Accumulate|Neutral)", t, re.I)
            fn = href.rsplit("/", 1)[-1]
            title = "%s - %s" % (company, "Pick of the Week" if rtype == "Pick of the Week" else "Top Monthly Pick")
            w.add(make_record(
                SRC, broker=BROKER, company=company, symbol=None, title=title, date=date,
                report_type=rtype, rating=rm.group(1) if rm else None,
                target=tm.group(1) if tm else None, price_at_reco=pm.group(1) if pm else None,
                summary=None, pdf_url=href, page_url=url))
            n += 1
    print(path, n)


def list_downloads(w, path, rtype_default, company=True):
    """pages made of '<Company (CODE)> Download pdf' rows (opportune, rating-monitor)."""
    url = f"{BASE}/fundamental-research-report/{path}/"
    b = soup(url)
    if not b:
        print("fail", url)
        return
    seen = set()
    n = 0
    for a in b.find_all("a", href=True):
        href = a["href"]
        if not (href.lower().endswith(".pdf") and "/uploads/" in href) or href in seen:
            continue
        if not re.match(r"download pdf", a.get_text(" ", strip=True), re.I):
            continue
        seen.add(href)
        row = a.parent
        label = None
        for _ in range(4):
            row_txt = row.get_text(" ", strip=True)
            lab = re.sub(r"\s*Download pdf\s*$", "", row_txt, flags=re.I).strip()
            if lab and len(lab) < 120:
                label = lab
                break
            row = row.parent
        if not label:
            continue
        name, code = split_name(label)
        fn = href.rsplit("/", 1)[-1]
        date = date_from_name(fn) or last_modified(href)
        w.add(make_record(
            SRC, broker=BROKER, company=name, symbol=None,
            title=re.sub(r"_[0-9a-f]{8,12}\.pdf$", "", fn).replace("_", " "),
            date=date, report_type=rtype_from_name(fn) if rtype_default is None else rtype_default,
            summary=("Kotak ticker code: %s" % code) if code else None,
            pdf_url=href, page_url=url))
        n += 1
    print(path, n)


def list_dated(w, path, base, rtype, title_prefix):
    """daily report pages: '<Mon yyyy> <dd Mon yyyy> Download pdf'."""
    url = f"{BASE}/{base}/{path}".rstrip("/") + "/"
    b = soup(url)
    if not b:
        print("fail", url)
        return
    seen = set()
    n = 0
    for a in b.find_all("a", href=True):
        href = a["href"]
        if not (href.lower().endswith(".pdf") and "/uploads/" in href) or href in seen:
            continue
        if not re.match(r"download pdf", a.get_text(" ", strip=True), re.I):
            continue
        seen.add(href)
        fn = href.rsplit("/", 1)[-1]
        date = date_from_name(fn)
        if not date:
            row = climb(a, "20", 3)
            m = re.search(r"\b(\d{1,2} \w{3} 20\d\d)", row.get_text(" ", strip=True)) if row else None
            date = norm_date(m.group(1)) if m else last_modified(href)
        w.add(make_record(
            SRC, broker=BROKER, company=None, title="%s %s" % (title_prefix, date), date=date,
            report_type=rtype, pdf_url=href, page_url=url))
        n += 1
    print(path or base, n)


def main():
    w = Writer(SRC)
    list_picks(w, "weekly-top-picks", "Pick of the Week")
    polite()
    list_picks(w, "monthly-top-picks", "Top Monthly Pick")
    polite()
    list_downloads(w, "opportune", None)
    polite()
    list_downloads(w, "rating-monitor", "Rating Monitor")
    polite()
    list_dated(w, "stock-recommendation-reports", "fundamental-research-report", "Stock Recommendations (daily)", "Kotak Stock Recommendations")
    polite()
    list_dated(w, "", "derivative-research-report", "Derivatives Daily", "Kotak Derivatives Daily")
    w.close()


if __name__ == "__main__":
    main()
