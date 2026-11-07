"""Choice Broking research -> data/raw/choiceindia.jsonl
API behind choiceindia.com/research-listing (found in the site JS):
POST https://finx.choiceindia.com/api/researchreport/v2/api/research-report-new
Returns Fundamental (institutional research PDFs) + Technical (Sumeet Bagadia desk calls, some with PDFs).
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import session, make_record, Writer, polite, clean

SRC = "choiceindia"
API = "https://finx.choiceindia.com/api/researchreport/v2/api/research-report-new"


def fix_url(u):
    if not u:
        return None
    u = u.replace("choiceindia.comresearchfiles", "choiceindia.com/researchfiles")
    return u


def rtype_of(x):
    blob = ((x.get("file_upload") or "") + " " + (x.get("plain_description") or "")[:200]).lower()
    if "initiat" in blob:
        return "Initiating Coverage"
    if "result" in blob or re.search(r"q[1-4]fy\d\d", blob):
        return "Result Update"
    if x["category_name"] == "Technical":
        return "Technical Call"
    return "Company Update"


def main():
    s = session()
    w = Writer(SRC)
    offset, limit, total = 0, 100, None
    while True:
        body = {"end_date": "", "is_expert": 0, "research_type": "", "limit": limit, "offset": offset,
                "segment": "EQ", "start_date": "", "status": "", "subcategory_id": "", "search": "",
                "id": "", "user_id": ""}
        r = s.post(API, json=body, headers={"Origin": "https://choiceindia.com",
                                             "Referer": "https://choiceindia.com/"}, timeout=60)
        j = r.json()
        rs = j["response"]["research"]
        total = j["response"].get("total_count")
        if not rs:
            break
        for x in rs:
            dp = {d["key"]: d["value"] for d in x.get("datapoints") or []}
            entry = dp.get("entry_price") or dp.get("cmp") or x.get("initial_cmp")
            tgt = dp.get("target")
            plain = (x.get("plain_description") or "").strip()
            if x["category_name"] == "Fundamental":
                title = clean(plain.split("\n")[0], 250) or clean(x.get("scrip_sec_desc"))
                summary = clean(" ".join(plain.split("\n")[1:]), 600) or clean(plain, 600)
            else:
                title = clean(plain, 250)
                summary = None
            call = (x.get("call_type") or "").split(",")[0].strip()
            page = f"https://finx.choiceindia.com/research-report/research/{'fundamental' if x['category_name']=='Fundamental' else 'experts'}/EQ/all/{x['id']}"
            w.add(make_record(
                SRC, broker="Choice Broking", company=clean(x.get("scrip_sec_desc")),
                symbol=x.get("scrip_symbol") or x.get("sec_name"),
                title=title, date=(x.get("published_date") or "")[:10],
                report_type=rtype_of(x), rating=call or None, target=tgt, price_at_reco=entry,
                summary=summary, pdf_url=fix_url(x.get("file_upload")), page_url=page,
                sector=None))
        offset += limit
        print(f"offset {offset}/{total} added={w.added}", flush=True)
        if total is not None and offset >= total:
            break
        polite(0.7)
    w.close()


if __name__ == "__main__":
    main()
