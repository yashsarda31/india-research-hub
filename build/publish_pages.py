"""Publish a public, links-only copy of the site to GitHub Pages (the gh-pages branch).

The public copy differs from your local site:
  - no PDFs and no report summaries: each report links to the publisher's own page or PDF
  - your in-house reports (scrapers/inhouse.py) are left out
  - Nirmal Bang links go to its research page, not straight past its sign-up form to the PDF

The branch is force-pushed as one fresh commit each time, so the repo history doesn't grow
with every data refresh.

    python build/publish_pages.py            # build _pages/ and push it
    python build/publish_pages.py --dry-run  # build _pages/ only
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scrapers"))
from common import MIN_DATE, ROOT  # noqa: E402

SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "_pages")
PRIVATE_SOURCES = {"inhouse"}
NO_DEEP_LINK_HOSTS = ("nirmalbang.com",)  # PDF sits behind the publisher's sign-up form


def git(*args, cwd=ROOT, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f"git {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout.strip()


def repo_https_url():
    url = git("remote", "get-url", "origin")
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return url, (f"https://github.com/{m.group(1)}" if m else None)


def build_public(repo_url):
    raw = open(os.path.join(SITE, "data.js"), encoding="utf-8").read()
    d = json.loads(raw[len("window.RH="):].rstrip().rstrip(";"))
    reports = []
    for r in d["reports"]:
        src = [s for s in r.get("src", []) if s not in PRIVATE_SOURCES]
        if not src or (r.get("d") or "") < MIN_DATE:
            continue
        r = {k: v for k, v in r.items() if k not in ("su", "lp")}
        r["src"] = src
        if r.get("pu") and any(h in r["pu"] for h in NO_DEEP_LINK_HOSTS):
            del r["pu"]
        reports.append(r)
    used = {r["s"] for r in reports if r.get("s")}
    meta = dict(d["meta"])
    meta.update({
        "public": True,
        "repo": repo_url,
        "n_reports": len(reports),
        "sources": {k: v for k, v in meta.get("sources", {}).items() if k not in PRIVATE_SOURCES},
        "source_counts": {k: v for k, v in meta.get("source_counts", {}).items() if k not in PRIVATE_SOURCES},
    })
    meta.pop("n_pdfs", None)
    payload = {"meta": meta, "stocks": {k: v for k, v in d["stocks"].items() if k in used}, "reports": reports}

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    with open(os.path.join(OUT, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.RH=")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    for fn in ("app.js", "style.css"):
        shutil.copy2(os.path.join(SITE, fn), os.path.join(OUT, fn))
    v = datetime.now().strftime("%Y%m%d%H%M%S")
    html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    html = re.sub(r'(src|href)="(data\.js|app\.js|style\.css)(\?v=\d+)?"', lambda m: f'{m.group(1)}="{m.group(2)}?v={v}"', html)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    kb = os.path.getsize(os.path.join(OUT, "data.js")) // 1024
    print(f"public build: {len(reports)} reports, {len(used)} stocks, "
          f"{sum(1 for r in reports if r.get('pu'))} direct PDF links, data.js {kb} KB -> {OUT}")
    return payload


def push(remote):
    name = git("config", "user.name", check=False) or "research-hub"
    email = git("config", "user.email", check=False) or "research-hub@users.noreply.github.com"
    tmp = tempfile.mkdtemp(prefix="rh-pages-")
    try:
        shutil.copytree(OUT, tmp, dirs_exist_ok=True)
        git("init", "-q", "-b", "gh-pages", cwd=tmp)
        git("config", "user.name", name, cwd=tmp)
        git("config", "user.email", email, cwd=tmp)
        git("add", "-A", cwd=tmp)
        msg = (f"Publish site {datetime.now():%Y-%m-%d %H:%M}\n\n"
               "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
        git("commit", "-q", "-m", msg, cwd=tmp)
        git("push", "-q", "--force", remote, "gh-pages", cwd=tmp)
        print("pushed gh-pages")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ensure_pages(repo_url):
    """Turn on GitHub Pages for the gh-pages branch (needs the gh CLI, first run only)."""
    slug = repo_url.split("github.com/")[1]
    chk = subprocess.run(["gh", "api", f"repos/{slug}/pages"], capture_output=True, text=True)
    if chk.returncode == 0:
        info = json.loads(chk.stdout)
        print("pages:", info.get("html_url"))
        return
    mk = subprocess.run(["gh", "api", "-X", "POST", f"repos/{slug}/pages",
                         "-f", "source[branch]=gh-pages", "-f", "source[path]=/"],
                        capture_output=True, text=True)
    print("pages enabled:" if mk.returncode == 0 else "could not enable pages:",
          (json.loads(mk.stdout).get("html_url") if mk.returncode == 0 else mk.stderr.strip()))


def main():
    remote, repo_url = repo_https_url()
    build_public(repo_url)
    if "--dry-run" in sys.argv:
        return
    push(remote)
    if repo_url:
        ensure_pages(repo_url)


if __name__ == "__main__":
    main()
