"""SBI Securities research. Public Angular app API research/getreports; payload/response are AES-CBC
with a hard-coded public key/iv shipped in the site's JS bundle (not authentication)."""
import sys, os, json, base64, re
from urllib.parse import quote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

K = b"12345678901234567890123456789012"; IV = b"1234567890123456"
API = "https://www.sbisecurities.in/apiconnect/research/getreports"
HDR = {"Content-Type": "application/json", "Origin": "https://www.sbisecurities.in",
       "Referer": "https://www.sbisecurities.in/research/fundamental", "client_id": "no-client"}

def enc(o): return base64.b64encode(AES.new(K, AES.MODE_CBC, IV).encrypt(pad(json.dumps(o).encode(), 16))).decode()
def dec(s): return unpad(AES.new(K, AES.MODE_CBC, IV).decrypt(base64.b64decode(s)), 16).decode()

# (category, sub, report_type, stock_specific). Daily derivative/technical/market-mirror dailies skipped (market noise).
SUBS = [("fundamental", "Pick Of the Day", "Stock Pick (Short Term)", True),
        ("fundamental", "Pick Of the Week", "Stock Pick (Weekly)", True),
        ("fundamental", "IPO notes", "IPO Note", True),
        ("fundamental", "Thematic Reports", "Thematic Report", False),
        ("fundamental", "Weekly Report", "Weekly Report", False),
        ("fundamental", "Daily Morning Update", "Morning Update", False),
        ("technical-derivatives", "Special Reports", "Special Report", False),
        ("technical-derivatives", "Weekly Indices View Point", "Weekly Indices View", False),
        ("technical-derivatives", "Roll-over Analysis", "Roll-over Analysis", False)]

def company_from(desc):
    d = re.sub(r"[_\s]*IPO Note\s*$", "", desc, flags=re.I)
    if "_" in d:
        c = d.split("_", 1)[1].strip(" ._")
        return c or None
    m = re.match(r"(?i)pick of the (?:day|week)\s*[-:]?\s*(.+)", d)
    return m.group(1).strip(" ._") if m else None

def main():
    s = session(); w = Writer("sbisec")
    for cat, sub, rtype, stock in SUBS:
        r = s.post(API, data=enc({"category_name": cat, "sub_category_name": sub}), headers=HDR, timeout=40)
        j = r.json()
        if not j.get("response"):
            print("empty", sub); continue
        data = json.loads(dec(j["response"])).get("data") or []
        n0 = w.added
        for x in data:
            d = norm_date(x.get("disp_date"))
            if not d or d < MIN_DATE: continue
            link = x.get("report_link")
            if not link: continue
            desc = x.get("report_desc") or ""
            co = company_from(desc) if stock else None
            w.add(make_record("sbisec", broker="SBI Securities", company=co, title=desc, date=d,
                report_type=rtype, rating=("BUY" if sub.startswith("Pick") else None),
                pdf_url=quote(link, safe=":/%"), page_url="https://www.sbisecurities.in/research"))
        print(sub, len(data), "added", w.added - n0, flush=True)
        polite(0.6)
    w.close()

if __name__ == "__main__":
    main()
