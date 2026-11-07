"""Geojit -> data/raw/geojit.jsonl
Geojit's stock research lives behind the Flip platform login (flip.geojit.com) and is not public;
geojit.com/research* are 404. The only public research artefact found is the monthly market-outlook
PDF https://www.geojit.com/misc/GI_<Month><YYYY>.pdf (no stock calls). We probe for those (strategy
notes, company=None, date = first of month since the PDF carries only month granularity).
"""
import os, sys, calendar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import session, make_record, Writer, polite


def main():
    s = session()
    w = Writer("geojit")
    for mi in range(1, 12):
        m = calendar.month_name[mi]
        u = f"https://www.geojit.com/misc/GI_{m}2026.pdf"
        try:
            r = s.get(u, timeout=60)
        except Exception as e:
            print("ERR", u, e); continue
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            w.add(make_record("geojit", broker="Geojit", title=f"Geojit Market Outlook - {m} 2026",
                              date=f"2026-{mi:02d}-01", report_type="Market Outlook",
                              pdf_url=u, page_url=u))
        polite(0.5)
    w.close()


if __name__ == "__main__":
    main()
