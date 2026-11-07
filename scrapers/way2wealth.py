"""Way2Wealth fundamental research (ASP.NET postback grid; categories Special Reports / Investment Ideas / Updates / Others).
PDFs are direct: https://www.way2wealth.com/Reports/<file>.pdf"""
import re, sys, os, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import session, make_record, Writer, polite, MIN_DATE, norm_date

SRC, BROKER = "way2wealth", "Way2Wealth"
URL = "https://www.way2wealth.com/research-details/fundamental-research"
CATS = {"3": "Special Reports", "1": "Investment Ideas", "2": "Updates", "4": "Others"}

def hidden(t):
    return {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"', t)}

def rows(t):
    out = []
    for m in re.finditer(r'grdreport_lblrdate_\d+">([^<]+)</span>.*?href="([^"]+\.pdf)".*?lblcap_\d+">(.*?)</span>(?:<br />\s*<span id="grdreport_lbldesc_\d+">(.*?)</span>)?', t, re.S):
        out.append((m.group(1), m.group(2), html.unescape(m.group(3)), html.unescape(m.group(4) or "")))
    return out

def rtype(t):
    for k in ["Result Update", "Initiating Coverage", "Company Update", "Quarterly Update", "Diwali Picks", "Update", "Idea"]:
        if k.lower() in t.lower(): return k
    return None

def main():
    s = session(); w = Writer(SRC)
    for cat, cname in CATS.items():
        t = s.get(URL).text
        st = hidden(t)
        sel = re.search(r'<select name="([^"]*ddlsubcat[^"]*)"', t).group(1)
        grid = re.search(r'name="([^"]*grdreport[^"]*)"', t)
        gname = "grdreport"
        if cat != "3":
            d = dict(st); d.update({"__EVENTTARGET": sel, "__EVENTARGUMENT": "", sel: cat})
            t = s.post(URL, data=d).text
        page = 1; seen_first = None
        while True:
            rs = rows(t)
            if not rs or rs[0][1] == seen_first: break
            seen_first = rs[0][1]
            oldest = "9"
            for dt, pdf, cap, desc in rs:
                d_ = norm_date(dt); oldest = min(oldest, d_ or "9")
                company = None
                m = re.match(r"(.+?(?:Ltd\.?|Limited|Bank|Inc\.?))\s*[-–]", cap)
                if m: company = m.group(1).strip()
                w.add(make_record(SRC, broker=BROKER, company=company, title=cap, date=d_, report_type=rtype(cap) or cname,
                                  summary=desc.rstrip(".") if desc else None, pdf_url=pdf, page_url=URL))
            print(cname, page, len(rs), oldest, w.added)
            if oldest < MIN_DATE: break
            page += 1
            if "Page$%d" % page not in t:
                # ellipsis jump: ask for next page anyway
                pass
            d = hidden(t); d.update({"__EVENTTARGET": gname, "__EVENTARGUMENT": "Page$%d" % page, sel: cat})
            t = s.post(URL, data=d).text; polite(0.6)
            if page > 200: break
    w.close()

if __name__ == "__main__":
    main()
