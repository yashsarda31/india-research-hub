"""Business Standard brokerage reports: listing embedded in __NEXT_DATA__ (response2.data)."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

URL = "https://www.business-standard.com/markets/research-report"
HOST = "https://bsmedia.business-standard.com"

def main():
    s = session(); w = Writer("bsreports")
    r = s.get(URL, timeout=60)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    data = json.loads(m.group(1))["props"]["pageProps"]["response2"]["data"]
    for x in data:
        d = norm_date(x.get("recommedation_date") or x.get("brokertips_date"))
        if not d or d < MIN_DATE:
            continue
        pdf = x.get("pdf_path")
        co = x.get("company_full_name") or x.get("company_name")
        w.add(make_record("bsreports", broker=x.get("broker_name"), company=co,
            title=f"{co} - {x.get('broker_name')} {x.get('action') or ''}".strip(), date=d,
            report_type="Broker Recommendation", rating=x.get("action"),
            target=x.get("target_price"), price_at_reco=x.get("price"),
            pdf_url=(HOST + pdf) if pdf else None, page_url=URL))
    w.close()

if __name__ == "__main__":
    main()
