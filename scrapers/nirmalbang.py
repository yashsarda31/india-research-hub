"""Nirmal Bang (NBIE institutional + NB retail research). Listing via /Ajaxpages/ResearchReports.aspx.
PDFs: https://www.nirmalbang.com/Upload/<file>.pdf (public; site UI shows a mobile-number prompt but the file is served without auth)."""
import html, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import session, make_record, Writer, polite, MIN_DATE, norm_date, clean

SRC, BROKER = "nirmalbang", "Nirmal Bang"
FEEDS = {49: "Institutional", 1: "Retail equity research"}
AJAX = "https://www.nirmalbang.com/Ajaxpages/ResearchReports.aspx?id=%d&pageNo=%d"
PAGE = {49: "https://www.nirmalbang.com/nb-research/institutional-research-reports.aspx",
        1: "https://www.nirmalbang.com/nb-research/equity-research-report-india.aspx"}
SKIP = re.compile(r"morning roundup|ai powered insights|daily report|bulk deal|expected result", re.I)

def rtype(t):
    for k in ["Result Update", "Initiating Coverage", "Management Meet", "Company Update", "Event Update", "Sector", "Diwali Picks", "Stock Picks"]:
        if k.lower() in t.lower():
            return k
    return None

def main():
    s = session(); w = Writer(SRC)
    for fid in FEEDS:
        pg, total = 1, 1
        while pg <= total and pg < 400:
            r = s.get(AJAX % (fid, pg), timeout=30)
            parts = r.text.split("*")
            body = parts[0]
            try: total = int(float(parts[1].strip().split()[0]))
            except Exception: pass
            secs = body.split('class="rsrchsec"')[1:]
            if not secs: break
            oldest = "9"
            for x in secs:
                m = re.search(r"<h2[^>]*>(.*?)</h2><span[^>]*>(.*?)</span>", x, re.S)
                f = re.search(r"ValidateResearchPDF\('([^']+)'", x)
                if not m: continue
                title = html.unescape(m.group(1)); d = norm_date(m.group(2).strip().replace("-26", "-2026") if re.search(r"-\d\d$", m.group(2).strip()) else m.group(2))
                if d: oldest = min(oldest, d)
                if SKIP.search(title) and fid == 49 and "(" not in title: continue
                pdf = "https://www.nirmalbang.com/Upload/" + f.group(1) if f else None
                company = sym = sector = None
                mm = re.match(r"(.+?)\s*\(([A-Z0-9&\-]{2,15})\)\s*-\s*([^|]+)\|\s*(.*)", title)
                if mm:
                    company, sym, sector = mm.group(1), mm.group(2), mm.group(3)
                summ = re.search(r"<p[^>]*>(.*?)</p>", x, re.S)
                w.add(make_record(SRC, broker=BROKER, company=company, symbol=sym, title=title, date=d,
                                  report_type=rtype(title), sector=sector, pdf_url=pdf, page_url=PAGE[fid],
                                  summary=html.unescape(summ.group(1)) if summ and summ.group(1).strip() else None))
            print(fid, pg, total, oldest, w.added)
            if oldest < MIN_DATE: break
            pg += 1; polite(0.6)
    w.close()

if __name__ == "__main__":
    main()
