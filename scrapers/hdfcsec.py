"""HDFC Securities public research -> data/raw/hdfcsec.jsonl

The retail 'calls' research (hdfcsec.com/research/calls, market-analysis-report) is
login-gated and its public ResearchAPI/GetResearchbyFilter feed ends in Mar 2025.
What IS public and current is the CMS feed behind
/research/equity/stock-research-institutional-reports :
    GET /api/cmsapi/GetNonCallResearch?schemeId=&compCode=&bucketId=<id>&pageNo=<n>&pagesize=<k>&fromDate=&toDate=
 bucket 1911 = Results Update, 1912 = Periodic Reports (Prime Research), 1913 = Institutional Reports (HSIE)
Response = 3 blocks: [0] article rows (PUBLISHED_ON dd-mm-yyyy), [1] paging, [2] predicate rows
(Title / Summary / UploadPdf / ActualContent). PDFs: https://www.hdfcsec.com/hsl.docs//<UploadPdf>
"""
import json
import os
import re
import sys
from urllib.parse import quote, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MIN_DATE, Writer, make_record, norm_date, session, polite  # noqa: E402

SRC = "hdfcsec"
BASE = "https://www.hdfcsec.com"
BUCKETS = {1911: "Results Update", 1912: "Periodic Report", 1913: "Institutional Report (HSIE)"}
PAGESIZE = 50
s = session()
H = {"X-Requested-With": "XMLHttpRequest",
     "Referer": BASE + "/research/equity/stock-research-institutional-reports"}


def fetch(bucket, page):
    url = (f"{BASE}/api/cmsapi/GetNonCallResearch?schemeId=&compCode=&bucketId={bucket}"
           f"&pageNo={page}&pagesize={PAGESIZE}&fromDate=&toDate=")
    for _ in range(3):
        try:
            r = s.get(url, headers=H, timeout=90)
            if r.status_code == 200:
                t = re.sub(r"^<string[^>]*>|</string>\s*$", "", r.text.strip())
                t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&") if t.startswith("&") else t
                return json.loads(t)
        except Exception as e:  # noqa: BLE001
            print("  retry", bucket, page, str(e)[:80])
        polite(2)
    return None


def dec(x):
    return unquote(x or "").replace("\r\n", " ").strip()


def parse_title(title, summary):
    company = None
    m = re.match(r"([^:–\-]{2,60}?)\s*:\s", title)
    if m:
        company = m.group(1).strip()
        if re.search(r"results daily|tracker|daily|weekly|monthly|strategy|outlook|review|hsie|prime", company, re.I):
            company = None
    text = title + " " + (summary or "")
    rating = None
    m = re.search(r"\b(?:maintain|initiate|initiating|upgrade|downgrade|reiterate|retain|assign)\w*\s+(?:a\s+|an\s+|our\s+)?(?:rating of\s+)?(BUY|SELL|ADD|REDUCE|HOLD|NEUTRAL|ACCUMULATE|OUTPERFORM|UNDERPERFORM)\b", text, re.I)
    if m:
        rating = m.group(1)
    m = re.search(r"(?:upgrade|downgrade|initiate|initiating)\w*\s+(?:to|with)?\s*(?:a\s+)?(BUY|SELL|ADD|REDUCE|HOLD|NEUTRAL|ACCUMULATE)", title, re.I)
    if m:
        rating = m.group(1)
    if re.search(r"results daily|tracker|sector|rollover|strategy|outlook|preview|monetary", title, re.I) and not company:
        return None, None, None
    if re.search(r"results daily", title, re.I):
        return None, None, None
    target = None
    m = re.search(r"(?:TP|target price|target)\s*(?:of)?\s*(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", text, re.I)
    if m:
        target = m.group(1)
    return company, rating, target


def main():
    w = Writer(SRC)
    for bucket, label in BUCKETS.items():
        page = 1
        total = 0
        while True:
            d = fetch(bucket, page)
            polite(0.8)
            if not d or not d[0].get("data") or not d[0]["data"][0]:
                break
            arts = d[0]["data"]
            preds = {}
            for p in d[2]["data"]:
                preds.setdefault(p["ARTICLE_ID"], {})[p["PREDICATE"]] = p["OBJECT1"]
            newest_old = True
            for a in arts:
                date = norm_date((a.get("PUBLISHED_ON") or "").split(" ")[0])
                if date and date >= MIN_DATE:
                    newest_old = False
                else:
                    continue
                pr = preds.get(a["ARTICLE_ID"], {})
                title = dec(pr.get("Title")) or a.get("TITLE")
                if a.get("TITLE") and len(a["TITLE"]) > len(title):
                    title = a["TITLE"]
                summary = dec(pr.get("Summary"))
                up = pr.get("UploadPdf")
                pdf = f"{BASE}/hsl.docs//{quote(up)}" if up else None
                company, rating, target = parse_title(title, summary)
                w.add(make_record(
                    SRC, broker="HDFC Securities", company=company, symbol=None, title=title, date=date,
                    report_type=label, rating=rating, target=target, summary=summary,
                    pdf_url=pdf, page_url=f"{BASE}/research/equity/stock-research-institutional-reports"))
                total += 1
            print(f"bucket {bucket} page {page}: {len(arts)} rows, kept so far {total}")
            if newest_old:  # whole page older than 2026 (feed is newest-first)
                break
            page += 1
    w.close()


if __name__ == "__main__":
    main()
