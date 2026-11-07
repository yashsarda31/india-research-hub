"""Shared helpers for every research-hub scraper.

Each scraper writes one JSON object per line to data/raw/<source>.jsonl using
make_record() so every source lands in the same schema. PDFs are NOT downloaded
by scrapers; build/download_pdfs.py fetches them centrally (dedupe + retries).

Schema (all keys always present; unknown -> None):
    source        short id of the site scraped, e.g. "icicidirect"
    broker        research house that authored the report, e.g. "ICICI Securities"
    company       company name as printed by the source
    symbol        NSE symbol if the source gives it (else None; merge step maps names)
    title         report title
    date          ISO yyyy-mm-dd publication date
    report_type   e.g. "Result Update", "Initiating Coverage", "Company Update"
    rating        BUY / SELL / HOLD / ACCUMULATE / ADD / REDUCE / NEUTRAL ... as given
    target        target price (float, rupees) or None
    price_at_reco price when the call was made (float) or None
    summary       short plain-text abstract (<= ~600 chars) or None
    pdf_url       DIRECT link to the PDF if publicly downloadable without login, else None
    page_url      landing page for the report (or the listing page it came from)
    sector        optional sector string
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# User rule: do not store any report older than 2026. Scrapers should also stop
# paginating once listings go past this date.
MIN_DATE = "2026-01-01"

FIELDS = ["source", "broker", "company", "symbol", "title", "date", "report_type",
          "rating", "target", "price_at_reco", "summary", "pdf_url", "page_url", "sector"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def session():
    """Browser-impersonating session (gets past most Cloudflare/Akamai checks)."""
    from curl_cffi import requests as cr
    return cr.Session(impersonate="chrome")


_DATE_FMTS = ["%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
              "%b %d, %Y", "%B %d, %Y", "%d %b, %Y", "%d %B, %Y", "%d.%m.%Y",
              "%Y-%m-%dT%H:%M:%S", "%d-%B-%Y", "%b. %d, %Y", "%d %b %y", "%d-%b-%y"]


def norm_date(s) -> str | None:
    """Best-effort parse of many date spellings to yyyy-mm-dd."""
    if s is None:
        return None
    if isinstance(s, (int, float)):  # epoch seconds or ms
        ts = s / 1000 if s > 1e11 else s
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    s = str(s).strip()
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    s = s.replace("Sept", "Sep")
    m = re.match(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        return m.group(0)
    for f in _DATE_FMTS:
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # trailing time / timezone noise
    s2 = re.split(r"\s+\d{1,2}:\d{2}", s)[0].strip(" ,")
    if s2 != s:
        return norm_date(s2)
    return None


def to_float(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if x == x else None
    t = re.sub(r"[^\d.\-]", "", str(x).replace(",", ""))
    try:
        v = float(t)
        return v if v > 0 else None
    except ValueError:
        return None


def clean(s, n=None):
    if s is None:
        return None
    s = re.sub(r"\s+", " ", str(s)).strip()
    if not s:
        return None
    if n and len(s) > n:
        s = s[: n - 1].rstrip() + "…"
    return s


def make_record(source, **kw) -> dict:
    rec = {k: None for k in FIELDS}
    rec["source"] = source
    for k, v in kw.items():
        if k not in rec:
            raise KeyError(f"unknown field {k}")
        rec[k] = v
    rec["date"] = norm_date(rec["date"]) if rec["date"] else None
    rec["target"] = to_float(rec["target"])
    rec["price_at_reco"] = to_float(rec["price_at_reco"])
    for k in ("broker", "company", "title", "report_type", "rating", "sector"):
        rec[k] = clean(rec[k], 300)
    rec["summary"] = clean(rec["summary"], 600)
    if rec["rating"]:
        rec["rating"] = rec["rating"].upper()
    return rec


class Writer:
    """Append-safe JSONL writer that skips duplicates (by pdf_url/page_url+title)."""

    def __init__(self, source: str, fresh: bool = False):
        self.path = os.path.join(RAW_DIR, f"{source}.jsonl")
        self.seen = set()
        if fresh and os.path.exists(self.path):
            os.remove(self.path)
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        self.seen.add(self.key(json.loads(line)))
                    except Exception:
                        pass
        self.f = open(self.path, "a", encoding="utf-8")
        self.added = 0
        self.too_old = 0

    @staticmethod
    def key(r):
        return (r.get("pdf_url") or "") + "|" + (r.get("page_url") or "") + "|" + (r.get("title") or "") + "|" + (r.get("date") or "")

    def add(self, rec: dict) -> bool:
        # Hard rule from the user: store nothing published before 2026.
        # Undated records are dropped too (can't prove they're 2026+).
        if not rec.get("date") or rec["date"] < MIN_DATE:
            self.too_old += 1
            return False
        k = self.key(rec)
        if k in self.seen:
            return False
        self.seen.add(k)
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.added += 1
        if self.added % 200 == 0:
            self.f.flush()
        return True

    def close(self):
        self.f.close()
        print(f"[{os.path.basename(self.path)}] +{self.added} new, {len(self.seen)} total, "
              f"{self.too_old} dropped as pre-2026/undated")


def polite(sec=0.6):
    time.sleep(sec)
