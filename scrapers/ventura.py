"""Ventura Securities (old site ventura1.com): Quarterly result-update PDFs (company-specific) + stock-idea PDFs.
Quarterly list: Research/Recommendation.aspx (ASP.NET postback, date range + pager). PDFs direct on ventura1.com."""
import re, sys, os, html
from urllib.parse import unquote
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import session, make_record, Writer, polite, MIN_DATE, norm_date

SRC, BROKER = "ventura", "Ventura Securities"
U = "https://www.ventura1.com/Research/Recommendation.aspx"
UI = "https://www.ventura1.com/Research/StockIdeaPg.aspx"
CP = "ctl00$ContentPlaceHolder1$"

def inputs(t):
    d = {}
    for m in re.finditer(r'<input[^>]*>', t):
        tag = m.group(0)
        if 'hidden' not in tag: continue
        n = re.search(r'name="([^"]+)"', tag); v = re.search(r'value="([^"]*)"', tag)
        if n: d[n.group(1)] = html.unescape(v.group(1)) if v else ''
    return d

def sels(h):
    d = {}
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', h, re.S):
        o = re.search(r'<option selected="selected" value="([^"]*)"', m.group(2)) or re.search(r'<option value="([^"]*)"', m.group(2))
        d[m.group(1)] = o.group(1) if o else ''
    return d

def rows(x):
    out = []
    for tr in re.findall(r'<tr>\s*<td class="GridDataCenter">(.*?)</tr>', x, re.S):
        c = re.findall(r'<td[^>]*>(.*?)</td>', '<td class="GridDataCenter">' + tr, re.S)
        if len(c) >= 3:
            u = re.search(r"href='([^']+)'", c[2])
            out.append((c[0].strip(), re.sub('<[^>]+>', '', c[1]).strip(), u.group(1) if u else None))
    return out

def rtype(pdf):
    n = unquote(pdf or "").lower()
    for k, v in [("initiat", "Initiating Coverage"), ("result", "Result Update"), ("update", "Company Update")]:
        if k in n: return v
    return "Result Update"

def main():
    s = session(); w = Writer(SRC)
    h = s.get(U).text
    d = inputs(h); d.update(sels(h))
    d.update({CP + "HiddenFromDate": "01-Jan-2026", CP + "HiddenToDate": datetime.now().strftime("%d-%b-%Y"),
              CP + "DateUsrCtl1$ddlYear": "2026", CP + "DateUsrCtl1$ddlMonth": "Jan", CP + "DateUsrCtl1$ddlDay": "01",
              CP + "DateUsrCtl2$ddlYear": str(datetime.now().year), CP + "DateUsrCtl2$ddlMonth": datetime.now().strftime("%b"),
              CP + "DateUsrCtl2$ddlDay": datetime.now().strftime("%d"), "__EVENTTARGET": CP + "A1"})
    x = s.post(U, data=d).text
    npages = len(re.findall(r'<option[^>]*value="\d+"', re.search(r'ddlPageSelector.*?</select>', x, re.S).group(0))) if 'ddlPageSelector' in x else 1
    page = 1
    while True:
        rs = rows(x); oldest = "9"
        for dt, name, pdf in rs:
            d_ = norm_date(dt); oldest = min(oldest, d_ or "9")
            w.add(make_record(SRC, broker=BROKER, company=name, title=(unquote(os.path.basename(pdf)).split("_", 1)[-1][:-4] if pdf else name),
                              date=d_, report_type=rtype(pdf), pdf_url=pdf, page_url=U))
        print("quarterly page", page, "/", npages, len(rs), oldest, w.added)
        if page >= npages or not rs or oldest < MIN_DATE: break
        d = inputs(x); d.update(sels(x)); d[CP + "btnNext"] = "Next >"
        x = s.post(U, data=d).text; page += 1; polite(0.7)
    # stock ideas / notes (date from .NET ticks in filename)
    t = s.get(UI).text
    for pdf in dict.fromkeys(re.findall(r'href="([^"]*stockideas[^"]+\.pdf)"', t)):
        fn = unquote(os.path.basename(pdf)); m = re.search(r"_(\d{18})\.pdf$", fn)
        if not m: continue
        dt = (datetime(1, 1, 1) + timedelta(microseconds=int(m.group(1)) // 10)).strftime("%Y-%m-%d")
        title = fn[:m.start()]
        comp = title.replace(" IPO note", "") if "IPO note" in title else None
        w.add(make_record(SRC, broker=BROKER, company=comp, title=title, date=dt,
                          report_type="IPO Note" if "IPO" in title else ("Daily Market Update" if "Daily Market" in title else "Stock Ideas"),
                          pdf_url=pdf, page_url=UI))
    w.close()

if __name__ == "__main__":
    main()
