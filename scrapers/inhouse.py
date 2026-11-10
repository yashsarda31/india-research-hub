"""Equity research reports already sitting in the user's Downloads folder.

Copies each PDF into pdfs/inhouse/ and writes data/raw/inhouse.jsonl with
pdf_url = "local:pdfs/inhouse/<file>". Rating is read off page 1 when printed.
Excluded on purpose: templates, the 2023 CPCL note (pre-2026), and the 2-page
mock notes headed "Goldman Sachs" (not actually Goldman research).
"""
import os
import re
import shutil

import fitz  # PyMuPDF

from common import ROOT, Writer, make_record

DL = os.path.join(os.path.expanduser("~"), "Downloads")  # paths below are relative to this
DEST = os.path.join(ROOT, "pdfs", "inhouse")
_INDEX = None


def locate(rel):
    """Downloads gets reorganised, so: exact path, else same filename anywhere under Downloads."""
    global _INDEX
    src = os.path.join(DL, rel)
    if os.path.exists(src):
        return src
    if _INDEX is None:
        _INDEX = {}
        for d, dirs, files in os.walk(DL):
            dirs[:] = [x for x in dirs if x not in ("node_modules", ".git", "research-hub") and not x.startswith(".")]
            for f in files:
                if f.lower().endswith(".pdf"):
                    _INDEX.setdefault(f, os.path.join(d, f))
    return _INDEX.get(os.path.basename(rel))

# (relative path, company, NSE symbol, date, title)
REPORTS = [
    ("Coding/Projects/keep/cipla_equity_research_report.pdf", "Cipla", "CIPLA", "2026-06-24", "Equity Research Report – Cipla Ltd"),
    ("Crizac-Equity-Research/Crizac-Equity-Research-2026-11-04.pdf", "Crizac", "CRIZAC", "2026-11-04", "Crizac: cheap on cash and earnings (initiating coverage)"),
    ("Finance/Reports/Equinox report source/Indian-Hotels-Equity-Research-2026-10-31.pdf", "Indian Hotels Company", "INDHOTEL", "2026-10-31", "Indian Hotels: strong franchise, demanding expectations"),
    ("happiest-minds-research-2026-11-04/output/pdf/Happiest-Minds-Equity-Research-2026-11-04.pdf", "Happiest Minds Technologies", "HAPPSTMNDS", "2026-11-04", "Happiest Minds: better margins; cash conversion and merger terms decide"),
    ("Hindustan-Zinc-Research-2026-11-03/output/pdf/Hindustan-Zinc-Equity-Research-2026-11-03.pdf", "Hindustan Zinc", "HINDZINC", "2026-11-03", "Hindustan Zinc: record earnings; price the cycle with care"),
    ("HUL-Equity-Research/HUL_Equity_Research_Report.pdf", "Hindustan Unilever", "HINDUNILVR", "2026-10-31", "Hindustan Unilever: equity research"),
    ("IndiaMART-Equity-Research/IndiaMART-Equity-Research-2026-11-04.pdf", "IndiaMART InterMESH", "INDIAMART", "2026-11-04", "IndiaMART: a cash machine priced for zero growth (initiating coverage)"),
    ("itc-research-2026-10-31/output/pdf/ITC-Equity-Research-31-Oct-2026.pdf", "ITC", "ITC", "2026-10-31", "ITC: independent equity research"),
    ("Jio_Financial_Services_Equity_Research_2026-10-20.pdf", "Jio Financial Services", "JIOFIN", "2026-10-20", "Jio Financial Services: platform build with fast lending growth"),
    ("Kotak-Equity-Research/Kotak-Mahindra-Bank-Equity-Research-2026-10-31.pdf", "Kotak Mahindra Bank", "KOTAKBANK", "2026-10-31", "Kotak Mahindra Bank: earnings are turning (initiating coverage)"),
    ("Lenskart-Research-2026-11-02/output/pdf/Equinox-Quantitative-Lenskart-Source-Matched.pdf", "Lenskart Solutions", "LENSKART", "2026-11-02", "Lenskart: strong execution, demanding expectations"),
    ("Maruti-Research-2026-11-03/Maruti-Suzuki-Equity-Research.pdf", "Maruti Suzuki India", "MARUTI", "2026-11-03", "Maruti Suzuki: record dispatches put the spotlight on margins"),
    ("NIIT-Learning-Research-2026-11-04/output/pdf/NIIT-Learning-Systems-Equity-Research-2026-11-04.pdf", "NIIT Learning Systems", "NIITMTS", "2026-11-04", "NIIT Learning Systems: valuation offers room for recovery"),
    ("Redington-Equity-Research/Redington-Equity-Research-2026-11-05.pdf", "Redington", "REDINGTON", "2026-11-05", "Redington: a record quarter, already priced (initiating coverage)"),
    ("redington-research-2026-10-20/output/pdf/Redington-Equity-Research-2026-10-20.pdf", "Redington", "REDINGTON", "2026-10-20", "Redington: independent research"),
    ("reliance-equity-research-2026-10-22/Reliance_Industries_Equity_Research_2026-10-22.pdf", "Reliance Industries", "RELIANCE", "2026-10-22", "Reliance Industries: equity research"),
    ("Tata-Consumer-Research-2026-10-31/output/Tata-Consumer-Products-Equity-Research-2026-10-31.pdf", "Tata Consumer Products", "TATACONSUM", "2026-10-31", "Tata Consumer Products: equity research"),
    ("shyam-metalics-research-2026-11-09/output/pdf/Equinox-Shyam-Metalics-2026-11-09.pdf", "Shyam Metalics and Energy", "SHYAMMETL", "2026-11-09", "Shyam Metalics: growth is real; cash conversion is the test (initiating coverage)"),
    ("Welspun-Living-Research-2026-11-04/output/pdf/Welspun-Living-Equinox-Research-2026-11-05.pdf", "Welspun Living", "WELSPUNLIV", "2026-11-05", "Welspun Living: recovery is real; the price asks for more"),
]

RATINGS = ["STRONG BUY", "BUY", "ACCUMULATE", "ADD", "OVERWEIGHT", "HOLD", "NEUTRAL",
           "REDUCE", "UNDERWEIGHT", "SELL"]


OVERRIDES = {("REDINGTON", "2026-11-05"): "REDUCE"}  # rating sits in a graphic on p1


def rating_from(text):
    # Only words printed in capitals count, so prose like "add" / "hold" is ignored.
    hits = [(m.start(), r) for r in RATINGS for m in [re.search(rf"\b{r}\b", text)] if m]
    return min(hits)[1] if hits else None


def main():
    os.makedirs(DEST, exist_ok=True)
    w = Writer("inhouse", fresh=True)
    for rel, company, sym, date, title in REPORTS:
        fn = f"{sym}-{date}.pdf"
        src = locate(rel)
        if src:
            shutil.copy2(src, os.path.join(DEST, fn))
        elif os.path.exists(os.path.join(DEST, fn)):
            src = os.path.join(DEST, fn)  # source moved/deleted: keep the copy we already have
            print("source not found, using stored copy", fn)
        else:
            print("missing", rel)
            continue
        doc = fitz.open(src)
        p1 = doc[0].get_text()
        summary = re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in doc[:2]))[:900]
        w.add(make_record(
            "inhouse", broker="In-house (my research)", company=company, symbol=sym,
            title=title, date=date, report_type="Equity Research",
            rating=OVERRIDES.get((sym, date)) or rating_from(p1[:1500]), summary=summary,
            pdf_url=f"local:pdfs/inhouse/{fn}", page_url=None))
    w.close()


if __name__ == "__main__":
    main()
