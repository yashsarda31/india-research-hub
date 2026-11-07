"""Download the NSE / NIFTY reference lists build_site.py uses to map company names to symbols.

Saves to data/ref/. Run once after cloning (update.py calls it when the files are missing).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scrapers"))
from common import ROOT, session  # noqa: E402

REF = os.path.join(ROOT, "data", "ref")
FILES = {
    "EQUITY_L.csv": "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    "SME_EQUITY_L.csv": "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv",
    "nifty500.csv": "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "niftytotalmarket.csv": "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
    "niftymicrocap250.csv": "https://niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
}


def main(force=False):
    os.makedirs(REF, exist_ok=True)
    s = session()
    for name, url in FILES.items():
        path = os.path.join(REF, name)
        if os.path.exists(path) and not force:
            continue
        r = s.get(url, timeout=60)
        if r.status_code == 200 and b"," in r.content[:200]:
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"saved {name} ({len(r.content) // 1024} KB)")
        else:
            print(f"failed {name}: HTTP {r.status_code}")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
