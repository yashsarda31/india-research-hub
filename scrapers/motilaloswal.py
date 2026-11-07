"""Motilal Oswal public research teasers + PDFs -> data/raw/motilaloswal.jsonl

motilaloswal.com/report/<slug>/<id> pages are client-rendered from
POST /prod/mocorporate/moapiservice/getresearchreportdetails whose body is
AES-CBC encrypted with a key/IV that the site itself serves as response headers
(esa-count / zend-count) of /zend-aes.js. We replay exactly what the page does,
walking report ids downward from the newest. The response contains a public
`reportpdf` URL (www.motilaloswal.com/site/...pdf). Publication date = `createdon`
if present, otherwise decoded from the .NET-ticks number in the PDF filename.
"""
import base64
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cryptography.hazmat.primitives import padding  # noqa: E402
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: E402
from common import MIN_DATE, Writer, make_record, norm_date, session, polite  # noqa: E402

SRC = "motilaloswal"
BASE = "https://www.motilaloswal.com"
API = BASE + "/prod/mocorporate/moapiservice/"
START_ID = 10320  # newest known id is ~10241 (2 Jan 2026); probe a bit above
STOP_AFTER_OLD = 40  # stop after this many consecutive pre-2026 reports

s = session()
H = {"accept": "text/plain", "Content-Type": "application/json"}
key = iv = None


def load_keys():
    global key, iv
    r = s.get(BASE + "/zend-aes.js", timeout=60)
    key = base64.b64decode(r.headers["esa-count"])
    iv = base64.b64decode(r.headers["zend-count"])


def enc(txt):
    p = padding.PKCS7(128).padder()
    d = p.update(txt.encode()) + p.finalize()
    c = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(c.update(d) + c.finalize()).decode()


def details(rid):
    body = json.dumps({"myRequest": enc(json.dumps({"reportid": rid}))})
    for _ in range(3):
        try:
            r = s.post(API + "getresearchreportdetails", headers=H, data=body, timeout=60)
            if r.status_code == 200:
                return (r.json().get("data") or [None])[0]
        except Exception as e:  # noqa: BLE001
            print("  retry", rid, str(e)[:60])
        polite(1.5)
    return None


def ticks_date(pdf):
    m = re.search(r"/(6\d{17})\.pdf", pdf or "")
    if not m:
        return None
    ts = int(m.group(1)) / 1e7 - 62135596800
    try:
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return None


def slug(t):
    t = t.lower().replace("&", "")
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"[^a-z0-9-]", "", t)
    return re.sub(r"-{2,}", "-", t)


def main():
    load_keys()
    w = Writer(SRC)
    old_run = 0
    empty_run = 0
    rid = START_ID
    seen = 0
    while rid > 0 and old_run < STOP_AFTER_OLD:
        d = details(rid)
        polite(0.5)
        if not d:
            rid -= 1
            empty_run += 1
            if empty_run > 400:
                break
            continue
        empty_run = 0
        seen += 1
        pdf = d.get("reportpdf")
        date = norm_date(d.get("createdon")) or ticks_date(pdf)
        if not date or date < MIN_DATE:
            old_run += 1
        else:
            old_run = 0
        if not date or date < MIN_DATE:
            rid -= 1
            continue
        if pdf:
            # the advertised PDFs currently 404 (site/rreports/*.pdf); only keep a link that really serves a PDF
            try:
                x = s.get(pdf, timeout=60, headers={"Referer": BASE + "/"})
                if not x.content.startswith(b"%PDF"):
                    pdf = None
            except Exception:  # noqa: BLE001
                pdf = None
        title = d.get("title") or ""
        content = (d.get("reportcontent") or "").replace(" | ", ". ").replace("|", ". ")
        cat = d.get("categoryname")
        rating = target = None
        m = re.search(r"\b(Buy|Sell|Neutral|Hold)\s+rating", content, re.I) or re.search(r"\b(Buy|Sell|Neutral)\b\s+(?:rating\s+)?(?:with|and|;)", content, re.I)
        if m:
            rating = m.group(1)
        m = re.search(r"(?:target price|TP)[^0-9]{0,12}(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)", content, re.I)
        if m:
            target = m.group(1)
        rtype = title.split(" - ")[0].strip() if " - " in title else cat
        w.add(make_record(
            SRC, broker="Motilal Oswal", company=None, symbol=None, title=title, date=date,
            report_type=rtype, rating=rating, target=target, summary=content,
            pdf_url=pdf if pdf and pdf.lower().endswith(".pdf") else None,
            page_url=f"{BASE}/report/{slug(title)}/{rid}", sector=cat))
        rid -= 1
    print("ids with data:", seen, "stopped at id", rid)
    w.close()


if __name__ == "__main__":
    main()
