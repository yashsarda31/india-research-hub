"""Download every public report PDF referenced in data/raw/*.jsonl.

- Only http(s) pdf_url values; "local:" (in-house) files are already on disk.
- Saves to pdfs/<source>/<sha1(url)[:16]>.pdf, verifies the %PDF magic bytes.
- Resumable: data/pdf_manifest.json records url -> {path, bytes} or {error}.
- Polite: at most PER_HOST concurrent requests per host.

    python build/download_pdfs.py [--sources a,b] [--retry-failed]
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scrapers"))
from common import MIN_DATE, ROOT  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
PDFS = os.path.join(ROOT, "pdfs")
MANIFEST = os.path.join(ROOT, "data", "pdf_manifest.json")
PER_HOST = 3
WORKERS = 16
MAX_BYTES = 60 * 1024 * 1024

# Per-source extra headers (filled in from what each scraper needed).
SOURCE_HEADERS: dict[str, dict] = {}

_local = threading.local()
_host_sem = defaultdict(lambda: threading.Semaphore(PER_HOST))
_lock = threading.Lock()


def sess():
    if not hasattr(_local, "s"):
        from curl_cffi import requests as cr
        _local.s = cr.Session(impersonate="chrome")
    return _local.s


def load_jobs(only=None):
    jobs = {}
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".jsonl"):
            continue
        src = fn[:-6]
        if only and src not in only:
            continue
        with open(os.path.join(RAW, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                u = r.get("pdf_url") or ""
                if not u.startswith("http") or (r.get("date") or "") < MIN_DATE:
                    continue
                jobs.setdefault(u, (src, r.get("page_url")))
    return jobs


def fetch(url, src, page_url):
    host = urlparse(url).netloc
    h = {"Accept": "application/pdf,*/*;q=0.8"}
    p = urlparse(page_url or url)
    h["Referer"] = page_url if page_url else f"{p.scheme}://{p.netloc}/"
    h.update(SOURCE_HEADERS.get(src, {}))
    rel = os.path.join(src, hashlib.sha1(url.encode()).hexdigest()[:16] + ".pdf")
    out = os.path.join(PDFS, rel)
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return url, {"path": rel.replace("\\", "/"), "bytes": os.path.getsize(out)}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    last = None
    for attempt in range(3):
        try:
            with _host_sem[host]:
                r = sess().get(url, headers=h, timeout=60, allow_redirects=True)
            if r.status_code == 200:
                b = r.content
                if b[:1024].lstrip().startswith(b"%PDF") or b"%PDF" in b[:1024]:
                    if len(b) > MAX_BYTES:
                        return url, {"error": f"too big {len(b)}"}
                    with open(out, "wb") as f:
                        f.write(b)
                    return url, {"path": rel.replace("\\", "/"), "bytes": len(b)}
                last = f"not pdf ({r.headers.get('content-type', '')[:40]})"
                break
            last = f"HTTP {r.status_code}"
            if r.status_code in (403, 404, 410):
                break
        except Exception as e:
            last = str(e)[:120]
        time.sleep(2 * (attempt + 1))
    return url, {"error": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--manifest", help="separate manifest file, for running two downloaders at once")
    a = ap.parse_args()
    ap_per_host = os.environ.get("RH_PER_HOST")
    if ap_per_host:
        global PER_HOST
        PER_HOST = int(ap_per_host)
    global MANIFEST
    if a.manifest:
        MANIFEST = os.path.join(ROOT, "data", a.manifest)
    only = set(a.sources.split(",")) if a.sources else None
    man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
    jobs = load_jobs(only)
    todo = {u: v for u, v in jobs.items()
            if u not in man or ("error" in man[u] and a.retry_failed)
            or ("path" in man[u] and not os.path.exists(os.path.join(PDFS, man[u]["path"])))}
    print(f"{len(jobs)} pdf urls, {len(todo)} to fetch", flush=True)
    # Round-robin across hosts so one slow host doesn't park every worker on its semaphore.
    by_host = defaultdict(list)
    for u, v in todo.items():
        by_host[urlparse(u).netloc].append((u, v))
    order = []
    while any(by_host.values()):
        for h in list(by_host):
            if by_host[h]:
                order.append(by_host[h].pop())
    done = ok = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(fetch, u, s, p) for u, (s, p) in order]
        for fu in as_completed(futs):
            u, res = fu.result()
            with _lock:
                man[u] = res
                done += 1
                ok += "path" in res
                if done % 100 == 0:
                    json.dump(man, open(MANIFEST, "w", encoding="utf-8"))
                    print(f"{done}/{len(todo)} ok={ok}", flush=True)
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"))
    errs = defaultdict(int)
    for u in todo:
        if "error" in man[u]:
            errs[(jobs[u][0], man[u]["error"][:30])] += 1
    print(f"done {done}, ok {ok}")
    for k, v in sorted(errs.items(), key=lambda x: -x[1])[:20]:
        print("  fail", k, v)


if __name__ == "__main__":
    main()
