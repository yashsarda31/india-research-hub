"""Merge every scraper's output into site/data.js.

Steps: load data/raw/*.jsonl -> drop anything before MIN_DATE -> normalise broker
names -> map company names to NSE symbols (EQUITY_L + SME + NIFTY lists) ->
merge the same report seen on several sites (symbol + broker + date) -> attach
downloaded PDFs from data/pdf_manifest.json -> write site/data.js.

    python build/build_site.py
"""
import csv
import difflib
import hashlib
import unicodedata
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scrapers"))
from common import MIN_DATE, ROOT  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
REF = os.path.join(ROOT, "data", "ref")
MANIFEST = os.path.join(ROOT, "data", "pdf_manifest.json")
OUT = os.path.join(ROOT, "site", "data.js")

SOURCE_LABELS = {
    "inhouse": "My research (Downloads)", "trendlyne": "Trendlyne", "bsreports": "Business Standard",
    "moneycontrol": "Moneycontrol", "etmarkets": "Economic Times", "icicidirect": "ICICI Direct",
    "hdfcsec": "HDFC Securities", "motilaloswal": "Motilal Oswal", "kotaksec": "Kotak Securities",
    "plindia": "PL Capital", "choiceindia": "Choice Broking", "geojit": "Geojit", "sharekhan": "Sharekhan",
    "axisdirect": "Axis Direct", "angelone": "Angel One", "sbisec": "SBI Securities",
    "anandrathi": "Anand Rathi",
}
# Lower number wins when two sites describe the same report.
SOURCE_PRIORITY = defaultdict(lambda: 5, {"inhouse": 0, "trendlyne": 9, "bsreports": 7,
                                          "moneycontrol": 7, "etmarkets": 8})

BROKER_ALIASES = [
    (r"icici ?(direct|securities|sec)|^isec$|i-sec", "ICICI Securities"),
    (r"hdfc ?(securities|sec)", "HDFC Securities"),
    (r"motilal|mofsl", "Motilal Oswal"),
    (r"kotak", "Kotak Securities"),
    (r"prabhudas|^pl capital|^pl india|^plindia", "Prabhudas Lilladher (PL Capital)"),
    (r"choice", "Choice Broking"),
    (r"geojit", "Geojit"),
    (r"share ?khan", "Sharekhan"),
    (r"equirus", "Equirus"),
    (r"incred", "InCred Equities"),
    (r"aditya birla money", "Aditya Birla Money"),
    (r"axis ?(direct|securities|sec|capital)", "Axis Securities"),
    (r"angel", "Angel One"),
    (r"sbi ?(securities|cap|capital)|sbicap", "SBI Securities"),
    (r"anand ?rathi", "Anand Rathi"),
    (r"nirmal ?bang", "Nirmal Bang"),
    (r"k ?r ?choksey|krchoksey", "KR Choksey"),
    (r"ventura", "Ventura Securities"),
    (r"arihant", "Arihant Capital"),
    (r"religare", "Religare Broking"),
    (r"lkp", "LKP Securities"),
    (r"bob ?cap|bobcaps", "BOB Capital Markets"),
    (r"idbi", "IDBI Capital"),
    (r"dolat", "Dolat Capital"),
    (r"centrum", "Centrum Broking"),
    (r"emkay", "Emkay Global"),
    (r"elara", "Elara Capital"),
    (r"yes ?sec", "Yes Securities"),
    (r"way2wealth", "Way2Wealth"),
    (r"jm ?fin", "JM Financial"),
    (r"nuvama|edelweiss", "Nuvama"),
    (r"asit ?c|acmiil", "Asit C. Mehta"),
    (r"ashika", "Ashika"),
    (r"mirae", "Mirae Asset"),
    (r"reliance sec", "Reliance Securities"),
    (r"bp ?wealth", "BP Wealth"),
    (r"deven ?choksey|dcfl", "Deven Choksey"),
    (r"hem sec", "Hem Securities"),
    (r"in-house", "In-house (my research)"),
]

POS = {"BUY", "STRONG BUY", "ACCUMULATE", "ADD", "OUTPERFORM", "OVERWEIGHT", "BUY ON DIPS",
       "TRADING BUY", "POSITIVE", "BUY ON DIP", "LONG TERM BUY", "SECTOR OUTPERFORM"}
NEU = {"HOLD", "NEUTRAL", "MARKET PERFORM", "EQUAL WEIGHT", "MARKETPERFORM", "SECTOR PERFORM", "NOT RATED"}
NEG = {"SELL", "REDUCE", "UNDERPERFORM", "UNDERWEIGHT", "NEGATIVE", "SELL ON RISE", "SECTOR UNDERPERFORM"}


def norm_broker(b):
    if not b:
        return "Unknown"
    low = b.lower().strip()
    for pat, name in BROKER_ALIASES:
        if re.search(pat, low):
            return name
    b = re.sub(r"\s+", " ", b).strip()
    return re.sub(r",?\s+(Ltd\.?|Limited|Pvt\.? Ltd\.?|Private Limited)$", "", b, flags=re.I)


STOP = {"ltd", "limited", "the", "india", "co", "company", "corporation", "corp", "corpn", "inc",
        "pvt", "private", "and", "of", "ind", "i"}
# Abbreviations brokers use in company names that a plain prefix test can't catch.
ABBR = {"inds": "industries", "engg": "engineering", "intl": "international", "labs": "laboratories",
        "hsg": "housing", "mfg": "manufacturing", "svcs": "services", "fin": "finance",
        "pharma": "pharmaceuticals", "tech": "technologies", "infra": "infrastructure"}
# Short names that never match the registered name.
ALIASES = {"sbi": "SBIN", "state bank": "SBIN", "hul": "HINDUNILVR", "ril": "RELIANCE",
           "lic": "LICI", "life insurance": "LICI", "zomato": "ETERNAL", "eternal": "ETERNAL",
           "paytm": "PAYTM", "nykaa": "NYKAA", "policybazaar": "POLICYBZR", "pb fintech": "POLICYBZR",
           "indigo": "INDIGO", "interglobe aviation": "INDIGO", "dmart": "DMART", "info edge": "NAUKRI",
           "ltimindtree": "LTIM", "icici pru life": "ICICIPRULI", "icici prudential life insurance": "ICICIPRULI",
           "icici lombard": "ICICIGI", "bank baroda": "BANKBARODA", "pnb": "PNB", "m and m": "M&M",
           "mahindra and mahindra": "M&M", "l and t": "LT", "larsen": "LT", "bajaj auto": "BAJAJ-AUTO",
           "adani port and sez": "ADANIPORTS", "adani ports": "ADANIPORTS", "max healthcare": "MAXHEALTH",
           "hdfc amc": "HDFCAMC", "nalco": "NATIONALUM", "ondeo nalco": None, "jsw infra": "JSWINFRA",
           "prestige estates": "PRESTIGE", "krishna institute": "KIMS", "krishna institu": "KIMS",
           "ongc": "ONGC", "oil natural gas": "ONGC", "gujarat state petronet": "GSPL",
           "sun pharma": "SUNPHARMA", "dr reddys": "DRREDDY", "cholamandalam": "CHOLAFIN",
           "pitti engg": "PITTIENG", "mold tek pack": "MOLDTKPAC", "navin fluo intl": "NAVINFLUOR",
           "one97 communications": "PAYTM", "one97": "PAYTM", "hind unilever": "HINDUNILVR",
           "hindustan unilever": "HINDUNILVR", "natl aluminium": "NATIONALUM", "cholaman inv": "CHOLAFIN",
           "kirl brothers": "KIRLOSBROS", "kirl oil": "KIRLOSENG", "irctc": "IRCTC", "nsdl": "NSDL",
           "national securities depository": "NSDL", "absl amc": "ABSLAMC"}


def norm_name(s, keep_common=False):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()  # Nestlé -> Nestle
    s = s.lower().replace("&", " and ").replace("'s ", "s ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    raw = [t for t in s.split() if keep_common or t not in ("and", "of")]
    toks, glue = [], False
    for t in raw:  # glue initials: "j k cement" -> "jk cement", "l t foods" -> "lt foods"
        if len(t) == 1 and t.isalpha() and glue:
            toks[-1] += t
            continue
        glue = len(t) == 1 and t.isalpha()
        toks.append(t)
    toks = [t for t in toks if keep_common or t not in STOP]
    return " ".join(toks)


def load_universe():
    stocks = {}  # SYM -> {name, industry}
    with open(os.path.join(REF, "EQUITY_L.csv"), encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            row = {k.strip(): (v or "").strip() for k, v in row.items()}
            stocks[row["SYMBOL"]] = {"name": row["NAME OF COMPANY"], "industry": None}
    p = os.path.join(REF, "SME_EQUITY_L.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                row = {k.strip().upper(): (v or "").strip() for k, v in row.items()}
                sym = row.get("SYMBOL")
                name = row.get("NAME_OF_COMPANY") or row.get("NAME OF COMPANY")
                if sym and name and sym not in stocks:
                    stocks[sym] = {"name": name, "industry": "SME"}
    for fn in ("niftytotalmarket.csv", "niftymicrocap250.csv", "nifty500.csv"):
        p = os.path.join(REF, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                sym = row["Symbol"].strip()
                if sym in stocks:
                    stocks[sym]["industry"] = row["Industry"].strip()
    return stocks


class Matcher:
    """Company name -> NSE symbol. Conservative: an unmatched name is better than a wrong one."""

    def __init__(self, stocks):
        self.stocks = stocks
        self.by_name = {}  # normalised registered name -> symbol
        for sym, v in stocks.items():  # names first so they beat symbol look-alikes
            n = norm_name(v["name"])
            if n:
                self.by_name.setdefault(n, sym)
        self.by_sym = {norm_name(s): s for s in stocks}
        self.first_tok = defaultdict(list)
        for k in self.by_name:
            self.first_tok[k.split()[0]].append(k)
        self.cache = {}

    @staticmethod
    def _tok_prefix(q, k):
        """every query token is a prefix of the matching name token, in order."""
        if len(q) > len(k):
            return False
        return all(kt.startswith(qt) or (qt in ABBR and kt.startswith(ABBR[qt])) for qt, kt in zip(q, k))

    def match(self, name):
        if not name:
            return None
        if name in self.cache:
            return self.cache[name]
        self.cache[name] = sym = self._match(name)
        return sym

    def _match(self, name):
        for sep in (" - ", ": ", "_"):  # "ITC Hotels - Good Q1…", "Amber Enterprises Ltd_03.08.2026"
            head = name.split(sep)[0]
            if head != name and len(head) >= 2:
                s = self._match(head)
                if s:
                    return s
        n = norm_name(name)
        if not n:
            return None
        loose = norm_name(name, keep_common=True)
        for key in (n, loose, " ".join(n.split()[:3]), " ".join(n.split()[:2])):
            if key in ALIASES:
                s = ALIASES[key]
                return s if s in self.stocks else None
        if n in self.by_name:
            return self.by_name[n]
        if name.strip().upper() in self.stocks:
            return name.strip().upper()
        if n in self.by_sym and len(n) >= 3 and " " not in n:
            return self.by_sym[n]  # e.g. "BHEL", "CDSL", "MCX"
        qt = n.split()
        cands = self.first_tok.get(qt[0], [])
        if not cands and len(qt[0]) >= 4 and len(qt) >= 2:  # abbreviated first word: "creditacc gram"
            cands = [k for t, ks in self.first_tok.items() if t.startswith(qt[0]) for k in ks]
        # 1) record name is a shortened registered name ("Max Healthcare" -> "max healthcare institute")
        # 2) abbreviations ("Kalpataru Proj." -> "kalpataru projects international")
        hits = {k for k in cands if self._tok_prefix(qt, k.split())}
        if len(hits) > 1:  # prefer exact token count, then the shortest
            same = [k for k in hits if len(k.split()) == len(qt)]
            hits = set(same) if len(same) == 1 else hits
        if len(hits) == 1:
            return self.by_name[hits.pop()]
        # 3) record name has extra words ("Zydus Lifesciences - Quest to…") – registered name >= 2 tokens
        longer = [k for k in cands if len(k.split()) >= 2 and n.startswith(k + " ")]
        if len(longer) == 1:
            return self.by_name[longer[0]]
        # 4) near-identical spelling, only among names sharing the first word
        best = difflib.get_close_matches(n, cands, n=1, cutoff=0.88)
        return self.by_name[best[0]] if best else None


def title_company(title):
    if not title:
        return None
    m = re.match(r"\s*([A-Za-z0-9&.' \-]{3,60}?)\s*(?::|\s[-–|]\s|\sQ[1-4]\s?FY|\s\(| - )", title)
    return m.group(1).strip() if m else None


def bucket(r):
    if not r:
        return None
    r = r.upper().strip()
    if r in POS or r.startswith("BUY"):
        return "pos"
    if r in NEU:
        return "neu"
    if r in NEG or r.startswith("SELL"):
        return "neg"
    return None


def main():
    stocks = load_universe()
    m = Matcher(stocks)
    man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}

    recs = []
    per_source = Counter()
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".jsonl"):
            continue
        with open(os.path.join(RAW, fn), encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not r.get("date") or r["date"] < MIN_DATE:
                    continue
                if r["date"] > datetime.now().strftime("%Y-%m-%d"):
                    continue  # bad parse into the future
                recs.append(r)
                per_source[r["source"]] += 1

    extra_names = {}  # non-NSE symbol -> name
    merged = {}
    for r in recs:
        sym = (r.get("symbol") or "").strip().upper() or None
        if sym and sym.endswith((".NS", ".BO")):
            sym = sym[:-3]
        if sym and sym not in stocks:
            alt = m.match(r.get("company"))
            if alt:
                sym = alt
            elif sym.isdigit() or not r.get("company"):
                sym = None
        if not sym:
            sym = m.match(r.get("company"))
        if not sym and not r.get("company"):
            tc = title_company(r.get("title"))
            cand = m.match(tc) if tc else None
            # only trust exact normalised hits from titles
            if cand and norm_name(tc) == norm_name(stocks[cand]["name"]):
                sym = cand
        if sym and sym not in stocks:
            extra_names[sym] = r.get("company") or sym
        broker = norm_broker(r.get("broker"))
        if sym:
            key = (sym, broker, r["date"])
        elif r.get("company"):
            key = ("~" + norm_name(r["company"]), broker, r["date"])
        else:
            key = ("", broker, r["date"], norm_name(r.get("title") or "", True)[:80])

        lp = None
        pu = r.get("pdf_url")
        if pu and pu.startswith("local:"):
            lp = "../" + pu[6:]
            pu = None
        elif pu:
            # downloader saves to a deterministic path, so check the disk directly
            rel = f"{r['source']}/{hashlib.sha1(pu.encode()).hexdigest()[:16]}.pdf"
            if os.path.exists(os.path.join(ROOT, "pdfs", rel)):
                lp = "../pdfs/" + rel
            elif pu in man and "path" in man[pu]:
                lp = "../pdfs/" + man[pu]["path"]
        tl_pdf = None
        if r["source"] == "trendlyne" and r.get("page_url"):
            mm = re.search(r"/posts/(\d+)", r["page_url"])
            if mm:
                tl_pdf = f"https://trendlyne.com/get-document/post/pdf/{mm.group(1)}/"

        new = {
            "s": sym, "c": r.get("company") if not sym else None, "b": broker, "d": r["date"],
            "t": r.get("title"), "ty": r.get("report_type"), "ra": r.get("rating"),
            "tp": r.get("target"), "pr": r.get("price_at_reco"), "su": r.get("summary"),
            "lp": lp, "pu": pu, "pg": r.get("page_url"), "tl": tl_pdf, "src": [r["source"]],
            "sec": r.get("sector"), "_p": SOURCE_PRIORITY[r["source"]],
        }
        if key not in merged:
            merged[key] = new
            continue
        old = merged[key]
        if r["source"] not in old["src"]:
            old["src"].append(r["source"])
        hi, lo = (new, old) if new["_p"] < old["_p"] else (old, new)
        out = dict(hi)
        for k in ("c", "t", "ty", "ra", "tp", "pr", "su", "lp", "pu", "pg", "tl", "sec"):
            if not out.get(k) and lo.get(k):
                out[k] = lo[k]
        if lo.get("su") and hi.get("su") and len(lo["su"]) > len(hi["su"]) * 1.5:
            out["su"] = lo["su"]
        out["src"] = old["src"]
        merged[key] = out

    reports = sorted(merged.values(), key=lambda x: (x["d"], x["b"]), reverse=True)
    used = Counter(r["s"] for r in reports if r["s"])
    stock_out = {}
    for sym in used:
        if sym in stocks:
            stock_out[sym] = [stocks[sym]["name"], stocks[sym]["industry"], 1]
        else:
            stock_out[sym] = [extra_names.get(sym, sym), None, 0]
    for r in reports:
        r.pop("_p", None)
        r["rb"] = bucket(r["ra"])
        for k in [k for k, v in r.items() if v in (None, "", [])]:
            del r[k]

    meta = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "min_date": MIN_DATE,
        "sources": {k: SOURCE_LABELS.get(k, k) for k in per_source},
        "source_counts": dict(per_source),
        "n_reports": len(reports),
        "n_pdfs": sum(1 for r in reports if r.get("lp")),
    }
    payload = {"meta": meta, "stocks": stock_out, "reports": reports}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.RH=")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    # cache-bust the scripts so a refreshed browser never shows yesterday's data.js / app.js
    idx = os.path.join(ROOT, "site", "index.html")
    v = datetime.now().strftime("%Y%m%d%H%M%S")
    html = open(idx, encoding="utf-8").read()
    html = re.sub(r'src="(data|app)\.js(\?v=\d+)?"', lambda mm: f'src="{mm.group(1)}.js?v={v}"', html)
    html = re.sub(r'href="style\.css(\?v=\d+)?"', f'href="style.css?v={v}"', html)
    open(idx, "w", encoding="utf-8").write(html)
    unmatched = Counter(r.get("c") for r in reports if not r.get("s") and r.get("c"))
    print(json.dumps(meta, indent=1))
    print(f"stocks covered: {len(stock_out)}; reports with symbol: {sum(1 for r in reports if r.get('s'))}")
    print(f"raw rows {len(recs)} -> merged {len(reports)}; data.js {os.path.getsize(OUT)/1e6:.1f} MB")
    print("top unmatched companies:", unmatched.most_common(25))


if __name__ == "__main__":
    main()
