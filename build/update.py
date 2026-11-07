"""Refresh everything: run every scraper, download new PDFs, rebuild site/data.js.

Scrapers are re-runnable (they de-dupe) and stop at MIN_DATE, so a refresh only
adds what is new. Each scraper gets a time limit so one stuck site can't block
the rest.

    python build/update.py            # all sources
    python build/update.py trendlyne  # just some
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCR = os.path.join(ROOT, "scrapers")
PY = sys.executable
LOG = os.path.join(ROOT, "data", "logs")
SKIP = {"common.py"}
TIMEOUT = 45 * 60


def run(args, name):
    os.makedirs(LOG, exist_ok=True)
    t = time.time()
    with open(os.path.join(LOG, f"{name}.log"), "w", encoding="utf-8") as f:
        try:
            p = subprocess.run([PY, "-u", *args], cwd=SCR, stdout=f, stderr=subprocess.STDOUT, timeout=TIMEOUT)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    tail = open(os.path.join(LOG, f"{name}.log"), encoding="utf-8", errors="ignore").read().strip().splitlines()[-1:]
    print(f"  {name:<16} rc={rc}  {time.time() - t:5.0f}s  {tail[0][:110] if tail else ''}", flush=True)


def main():
    only = set(sys.argv[1:])
    scrapers = sorted(f for f in os.listdir(SCR) if f.endswith(".py") and f not in SKIP)
    if only:
        scrapers = [f for f in scrapers if f[:-3] in only]
    if not os.path.exists(os.path.join(ROOT, "data", "ref", "EQUITY_L.csv")):
        print("Fetching NSE reference lists…", flush=True)
        run([os.path.join(HERE, "fetch_ref.py")], "fetch_ref")
    print(f"Running {len(scrapers)} scrapers…", flush=True)
    for f in scrapers:
        run([f], f[:-3])
    print("Downloading new PDFs…", flush=True)
    run([os.path.join(HERE, "download_pdfs.py")], "download_pdfs")
    print("Building site…", flush=True)
    run([os.path.join(HERE, "build_site.py")], "build_site")
    print("Done. Open site/index.html (or run serve.bat).")


if __name__ == "__main__":
    main()
