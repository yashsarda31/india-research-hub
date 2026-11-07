# India Research Hub

A local, searchable library of 2026 research reports on Indian stocks. It scrapes broker websites
and aggregators, downloads the public report PDFs, maps every report to its NSE symbol, and builds a
static website. Type a stock name, even with a typo, and see every broker's report on it: rating,
target, implied move, summary and the PDF.

**Live site: https://yashsarda31.github.io/india-research-hub/**
The live site is the public, links-only version. Each report opens at the publisher's own page or PDF.

The first build (7 Nov 2026) found **15,523 reports** on **967 stocks** from **43 brokers**, and
saved 8,701 PDFs locally.

> The repo contains the code only. The PDFs and scraped data are copyrighted by their publishers and
> come to several GB, so they aren't committed. Run the build below to create your own copy.

## Setup
```bash
pip install -r requirements.txt
update.bat              # or: python build/update.py
```
`update.bat` fetches the NSE symbol lists, runs every scraper, downloads new PDFs into `pdfs/` and
writes `site/data.js`. The first run takes a while (PDF downloads are rate-limited per site). Later
runs only add what's new.

## Open it
Double-click `site/index.html`, or run `serve.bat` (http://127.0.0.1:8790/site/).
`/` focuses the search box. Each stock page shows:
- the latest call from each broker
- the buy/hold/sell split
- the median target and the implied move
- a chart of targets through 2026
- every report, with filters

## Publish the public site
`publish.bat` (or `python build/publish_pages.py`) builds a links-only copy in `_pages/` and
force-pushes it to the `gh-pages` branch as a single commit, so the history doesn't grow. It also
turns on GitHub Pages the first time. To refresh the data and publish in one go, run
`update.bat --publish`. The public copy:
- leaves out PDFs and summaries, and links to the original instead;
- leaves out in-house reports;
- doesn't deep-link past a publisher's sign-up form (Nirmal Bang).

## Sources
| Works | Notes |
|---|---|
| Trendlyne | all brokers, with ratings, targets and summaries; PDFs need a free Trendlyne login |
| Moneycontrol, Business Standard | broker reports with public PDFs (Motilal Oswal, JM, Emkay, PL…) |
| PL Capital, Axis Direct, Nirmal Bang, SBI Securities, Ventura, Choice, HDFC Securities, Kotak, Way2Wealth, ICICI Direct | brokers' own research pages |
| Sharekhan | listing only; its PDFs need an OTP login |
| `scrapers/inhouse.py` | your own research PDFs from the parent folder |

Skipped because they need a login or have no public 2026 listing: Geojit, Angel One, Anand Rathi,
Emkay (direct), Arihant, KR Choksey, Religare, and Motilal Oswal's own site.

## Rules baked in
- **Nothing dated before 1 Jan 2026 is stored.** `MIN_DATE` in `scrapers/common.py` sets the cutoff.
  The writer, the downloader and the site builder all enforce it, and undated reports are dropped.
- Only public pages and public PDFs are used. There are no logins, no CAPTCHA solving and no paywalled content.
- Downloads are polite: a few concurrent requests per host, round-robin across sites.

## Layout
```
scrapers/      one file per source; each writes data/raw/<source>.jsonl (shared schema in common.py)
build/         fetch_ref.py · download_pdfs.py · build_site.py · update.py · publish_pages.py
site/          index.html · app.js · style.css  (+ data.js, generated)
data/, pdfs/   generated locally, git-ignored
```
To add a source, write `scrapers/<id>.py` that calls `common.make_record()` and `common.Writer`.
`update.py` picks it up automatically.

Reports remain the property of their publishers. This tool is for personal reference only and is
not investment advice.
