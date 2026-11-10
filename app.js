(() => {
  "use strict";
  const D = window.RH || { meta: {}, stocks: {}, reports: [] };
  const R = D.reports;
  const S = D.stocks;
  // Public (GitHub Pages) build: no local PDFs or summaries, links go to the publishers.
  const PUB = !!(D.meta && D.meta.public);
  const hasPdf = (r) => (PUB ? !!r.pu : !!r.lp);
  const $ = (s, el = document) => el.querySelector(s);
  const view = $("#view");

  /* ---------- helpers ---------- */
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const safeUrl = (u) => (u && (/^https?:\/\//i.test(u) || /^\.\.\/pdfs\//.test(u)) ? u : null);
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtD = (d) => (d ? `${d.slice(8, 10)} ${MON[+d.slice(5, 7) - 1]} ${d.slice(0, 4)}` : "");
  const inr = (v) => (v == null ? "–" : "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: v < 100 ? 2 : 0 }));
  const num = (v) => Number(v).toLocaleString("en-IN");
  const pct = (v) => (v > 0 ? "+" : "") + v.toFixed(1) + "%";
  const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const today = new Date().toISOString().slice(0, 10);
  const daysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
  const enc = encodeURIComponent;
  const BUCKET_LABEL = { pos: "Buy-side", neu: "Hold / Neutral", neg: "Sell-side" };

  const ICON = {
    pdf: '<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h9l5 5v15H6z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M14 2v6h6" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    ext: '<svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    lock: '<svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  };

  /* ---------- indexes ---------- */
  const byKey = new Map(); // stock key -> [report]
  const byBroker = new Map();
  const nameOf = new Map();
  for (const r of R) {
    const k = r.s || (r.c ? "~" + r.c : null);
    if (k) {
      if (!byKey.has(k)) byKey.set(k, []);
      byKey.get(k).push(r);
      if (!nameOf.has(k)) nameOf.set(k, r.s ? (S[r.s] ? S[r.s][0] : r.s) : r.c);
    }
    if (!byBroker.has(r.b)) byBroker.set(r.b, []);
    byBroker.get(r.b).push(r);
  }
  const stockKey = (r) => r.s || (r.c ? "~" + r.c : null);
  const prettyName = (n) => (n || "").replace(/\s+(Limited|Ltd\.?)$/i, "");

  const entries = [];
  for (const [k, list] of byKey) {
    const sym = k.startsWith("~") ? null : k;
    const name = prettyName(nameOf.get(k));
    const nl = name.toLowerCase();
    entries.push({
      k, sym, name, n: list.length, nl,
      words: nl.split(/[^a-z0-9&]+/).filter(Boolean),
      compact: nl.replace(/[^a-z0-9]/g, "") + "|" + (sym || "").toLowerCase(),
      ind: sym && S[sym] ? S[sym][1] : null,
    });
  }
  const brokers = [...byBroker.entries()].map(([b, l]) => ({ b, n: l.length, bl: b.toLowerCase() })).sort((a, b) => b.n - a.n);

  function lev(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      let best = i;
      for (let j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      prev = cur;
    }
    return prev[b.length];
  }

  function score(e, q, qt, qc) {
    const sym = e.sym ? e.sym.toLowerCase() : "";
    let s = 0;
    if (sym && sym === qc) s = 1000;
    else if (e.nl === q) s = 950;
    else if (sym && sym.startsWith(qc)) s = 720 - Math.min(sym.length - qc.length, 20);
    else if (e.nl.startsWith(q)) s = 680;
    else if (qt.every((t) => e.words.some((w) => w.startsWith(t)))) s = 520;
    else if (e.nl.includes(q)) s = 420;
    else if (qc.length >= 3 && e.compact.includes(qc)) s = 380;
    else if (q.length >= 4) {
      const max = q.length >= 8 ? 2 : 1;
      let best = max + 1;
      for (const w of [e.nl, ...e.words, sym]) {
        if (!w) continue;
        best = Math.min(best, lev(q, w.slice(0, q.length + 1), max), lev(q, w, max));
        if (!best) break;
      }
      if (best <= max) s = 260 - best * 60;
    }
    return s ? s + Math.min(e.n, 60) : 0;
  }

  function searchStocks(raw, limit = 8) {
    const q = raw.toLowerCase().trim().replace(/\s+/g, " ");
    if (!q) return [];
    const qt = q.split(" ");
    const qc = q.replace(/[^a-z0-9&]/g, "");
    const out = [];
    for (const e of entries) {
      const s = score(e, q, qt, qc);
      if (s) out.push([s, e]);
    }
    out.sort((a, b) => b[0] - a[0] || b[1].n - a[1].n);
    return out.slice(0, limit).map((x) => x[1]);
  }

  /* ---------- autocomplete ---------- */
  const qi = $("#q");
  const ac = $("#ac");
  let acItems = [];
  let acSel = 0;

  function renderAC() {
    const v = qi.value.trim();
    if (!v) { ac.hidden = true; qi.parentElement.setAttribute("aria-expanded", "false"); return; }
    const st = searchStocks(v, 8);
    const vl = v.toLowerCase();
    const br = brokers.filter((b) => b.bl.includes(vl)).slice(0, 3);
    acItems = [];
    let html = "";
    if (st.length) {
      html += '<li class="grp" aria-hidden="true">Stocks</li>';
      for (const e of st) {
        acItems.push("#/s/" + enc(e.k));
        html += `<li role="option" data-i="${acItems.length - 1}"><span class="sym">${esc(e.sym || "unlisted")}</span><span class="nm">${esc(e.name)}</span><span class="ct">${e.n} report${e.n > 1 ? "s" : ""}</span></li>`;
      }
    }
    if (br.length) {
      html += '<li class="grp" aria-hidden="true">Brokers</li>';
      for (const b of br) {
        acItems.push("#/b/" + enc(b.b));
        html += `<li role="option" data-i="${acItems.length - 1}"><span class="sym">broker</span><span class="nm">${esc(b.b)}</span><span class="ct">${num(b.n)}</span></li>`;
      }
    }
    acItems.push("#/all?q=" + enc(v));
    html += `<li role="option" data-i="${acItems.length - 1}"><span class="sym">text</span><span class="nm">Search all report titles &amp; summaries for “${esc(v)}”</span></li>`;
    ac.innerHTML = html;
    acSel = 0;
    markSel();
    ac.hidden = false;
    qi.parentElement.setAttribute("aria-expanded", "true");
  }
  function markSel() {
    ac.querySelectorAll("li[data-i]").forEach((li) => li.classList.toggle("sel", +li.dataset.i === acSel));
    const s = ac.querySelector("li.sel");
    if (s) s.scrollIntoView({ block: "nearest" });
  }
  function go(h) { ac.hidden = true; qi.blur(); location.hash = h; }
  qi.addEventListener("input", renderAC);
  qi.addEventListener("focus", () => qi.value && renderAC());
  qi.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { acSel = Math.min(acSel + 1, acItems.length - 1); markSel(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { acSel = Math.max(acSel - 1, 0); markSel(); e.preventDefault(); }
    else if (e.key === "Enter") { if (acItems.length) go(acItems[acSel]); e.preventDefault(); }
    else if (e.key === "Escape") { ac.hidden = true; qi.blur(); }
  });
  ac.addEventListener("mousedown", (e) => {
    const li = e.target.closest("li[data-i]");
    if (li) { e.preventDefault(); go(acItems[+li.dataset.i]); }
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".search")) ac.hidden = true; });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== qi && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) {
      e.preventDefault(); qi.focus(); qi.select();
    }
  });

  /* ---------- report rows ---------- */
  function ratingPill(r) {
    if (!r.ra) return "";
    return `<span class="pill ${r.rb || ""}">${esc(r.ra)}</span>`;
  }
  function rowHTML(r, showStock) {
    const k = stockKey(r);
    const lp = safeUrl(r.lp), pg = safeUrl(r.pg), pu = safeUrl(r.pu), tl = safeUrl(r.tl);
    const btns = [];
    if (lp) btns.push(`<a class="btn primary" href="${esc(lp)}" target="_blank" rel="noopener">${ICON.pdf}Open PDF</a>`);
    else if (pu) btns.push(`<a class="btn primary" href="${esc(pu)}" target="_blank" rel="noopener noreferrer">${ICON.pdf}PDF</a>`);
    if (!lp && !pu && tl) btns.push(`<a class="btn" href="${esc(tl)}" target="_blank" rel="noopener noreferrer" title="Needs a free Trendlyne login">${ICON.lock}PDF (Trendlyne)</a>`);
    if (pg) btns.push(`<a class="btn" href="${esc(pg)}" target="_blank" rel="noopener noreferrer">${ICON.ext}Source</a>`);
    let nums = "";
    if (r.tp) {
      const up = r.pr ? ((r.tp / r.pr - 1) * 100) : null;
      nums = `<div class="num">Target <b>${inr(r.tp)}</b>${up != null && isFinite(up) ? `<br>${pct(up)} vs ${inr(r.pr)} at call` : ""}</div>`;
    }
    const stockBit = showStock && k
      ? `<a class="stk" href="#/s/${enc(k)}">${esc(r.s || prettyName(r.c))}</a>`
      : (showStock && r.sec ? `<span class="stk">${esc(r.sec)}</span>` : "");
    const srcs = (r.src || []).map((s) => (D.meta.sources || {})[s] || s).join(" · ");
    return `<li class="r">
      <div class="dt">${fmtD(r.d)}</div>
      <div class="main">
        <div class="ttl">${esc(r.t || ((r.s || r.c || "") + " – report"))}</div>
        <div class="meta">${stockBit}<a href="#/b/${enc(r.b)}">${esc(r.b)}</a>${ratingPill(r)}${r.ty ? `<span>${esc(r.ty)}</span>` : ""}<span class="src">via ${esc(srcs)}</span></div>
        ${r.su ? `<p class="su clip" title="Click to expand">${esc(r.su)}</p>` : ""}
      </div>
      <div class="acts">${nums}<div class="btns">${btns.join("")}</div></div>
    </li>`;
  }

  /* list with filters + paging. opts: {showStock, title, q, controls:[...]} */
  function listView(host, list, opts = {}) {
    const st = Object.assign({ q: "", b: "", r: "", pdf: false, days: "" , ty: ""}, opts.state || {});
    const PAGE = 60;
    let shown = PAGE;
    const brokerOpts = opts.noBroker ? "" : (() => {
      const c = new Map();
      for (const r of list) c.set(r.b, (c.get(r.b) || 0) + 1);
      return [...c.entries()].sort((a, b) => b[1] - a[1]).map(([b, n]) => `<option value="${esc(b)}"${st.b === b ? " selected" : ""}>${esc(b)} (${n})</option>`).join("");
    })();
    host.innerHTML = `
      <div class="filters">
        ${opts.noText ? "" : `<input type="text" placeholder="Filter by title, stock, broker or words in the summary…" value="${esc(st.q)}" data-f="q">`}
        ${opts.noBroker ? "" : `<select data-f="b" aria-label="Broker"><option value="">All brokers</option>${brokerOpts}</select>`}
        <select data-f="days" aria-label="Period">
          <option value="">All of 2026</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option>
        </select>
        <button class="chip" data-r="pos" type="button">Buy</button>
        <button class="chip" data-r="neu" type="button">Hold</button>
        <button class="chip" data-r="neg" type="button">Sell</button>
        <button class="chip" data-pdf type="button">${ICON.pdf} ${PUB ? "Has PDF" : "PDF saved"}</button>
        <span class="count"></span>
      </div>
      <ul class="rlist"></ul>
      <button class="more" type="button" hidden>Show more</button>`;
    const ul = $(".rlist", host), more = $(".more", host), cnt = $(".count", host);
    const sel = $("select[data-f=days]", host);
    if (sel) sel.value = st.days;
    let cur = [];
    function apply() {
      const q = st.q.toLowerCase().trim();
      const qt = q ? q.split(/\s+/) : [];
      const since = st.days ? daysAgo(+st.days) : "";
      cur = list.filter((r) => {
        if (st.b && r.b !== st.b) return false;
        if (st.r && r.rb !== st.r) return false;
        if (st.pdf && !hasPdf(r)) return false;
        if (since && r.d < since) return false;
        if (qt.length) {
          const hay = (r._h ||= [r.t, r.s, r.c, r.b, r.ty, r.ra, r.su, r.sec, r.s && S[r.s] ? S[r.s][0] : ""].join(" ").toLowerCase());
          if (!qt.every((t) => hay.includes(t))) return false;
        }
        return true;
      });
      shown = PAGE;
      draw();
      host.querySelectorAll(".chip[data-r]").forEach((c) => c.classList.toggle("on", c.dataset.r === st.r));
      $(".chip[data-pdf]", host).classList.toggle("on", st.pdf);
      if (opts.onState) opts.onState(st);
    }
    function draw() {
      ul.innerHTML = cur.length ? cur.slice(0, shown).map((r) => rowHTML(r, opts.showStock)).join("") : `<li class="empty">No reports match these filters.</li>`;
      cnt.textContent = `${num(cur.length)} report${cur.length === 1 ? "" : "s"}`;
      more.hidden = cur.length <= shown;
      more.textContent = `Show more (${num(cur.length - shown)} left)`;
    }
    let t;
    host.addEventListener("input", (e) => {
      const f = e.target.dataset.f;
      if (!f) return;
      st[f] = e.target.value;
      clearTimeout(t);
      t = setTimeout(apply, f === "q" ? 140 : 0);
    });
    host.addEventListener("click", (e) => {
      const c = e.target.closest(".chip");
      if (c) {
        if (c.dataset.r) st.r = st.r === c.dataset.r ? "" : c.dataset.r;
        else st.pdf = !st.pdf;
        apply();
        return;
      }
      const su = e.target.closest(".su");
      if (su) su.classList.toggle("clip");
    });
    more.addEventListener("click", () => { shown += PAGE * 2; draw(); });
    apply();
  }

  /* ---------- views ---------- */
  function setNav(which) {
    document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("on", a.getAttribute("href") === which));
  }

  function home() {
    setNav("");
    if (!window.RH) {
      view.innerHTML = `<section class="hero"><h1>No reports built yet.</h1>
        <p>This copy has no data file. Run <span class="kbd">pip install -r requirements.txt</span> and then
        <span class="kbd">update.bat</span> (or <span class="kbd">python build/update.py</span>) from the project folder to scrape the sources,
        download the PDFs and build <span class="kbd">site/data.js</span>. Then reload this page.</p></section>`;
      return;
    }
    const m = D.meta;
    const nStocks = entries.filter((e) => e.sym).length;
    const since90 = daysAgo(90);
    const recent = new Map();
    for (const r of R) { if (r.d >= since90 && r.s) recent.set(r.s, (recent.get(r.s) || 0) + 1); }
    const top = [...recent.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15);
    const topMax = top.length ? top[0][1] : 1;
    const srcRows = Object.entries(m.source_counts || {}).sort((a, b) => b[1] - a[1]);
    const first = R.length ? R[R.length - 1].d : "";
    view.innerHTML = `
      <section class="hero">
        <h1>Every 2026 research report on Indian stocks, in one place.</h1>
        <p>${PUB
          ? `Search any NSE stock to see what each broker published on it: rating, target price and a link to the original report. Collected from ${Object.keys(m.sources || {}).length} public sources, ${fmtD(first)} to ${fmtD(R.length ? R[0].d : "")}. Updated ${fmtD((m.generated || "").slice(0, 10))}.`
          : `Search any NSE stock to see each broker's reports on it: rating, target price, summary and the PDF. Collected from ${Object.keys(m.sources || {}).length} sources, ${fmtD(first)} to ${fmtD(R.length ? R[0].d : "")}.`}</p>
        <div class="stats">
          <div class="stat"><b>${num(R.length)}</b><span>research reports</span></div>
          <div class="stat"><b>${num(nStocks)}</b><span>stocks covered</span></div>
          <div class="stat"><b>${num(brokers.length)}</b><span>brokers &amp; research houses</span></div>
          <div class="stat"><b>${num(PUB ? R.filter((r) => r.pu).length : (m.n_pdfs || 0))}</b><span>${PUB ? "direct PDF links" : "PDFs saved on this computer"}</span></div>
        </div>
      </section>
      <div class="grid2">
        <section class="card"><h2>Latest reports</h2><div id="latest"></div></section>
        <aside class="side">
          <section class="card"><h2>Most covered · last 90 days</h2>
            <ul class="toplist">${top.map(([s, n]) => `<li><a href="#/s/${enc(s)}"><span class="nm">${esc(prettyName(S[s] ? S[s][0] : s))}</span><span class="bar" style="width:${Math.max(8, (n / topMax) * 60)}px"></span><span class="n">${n}</span></a></li>`).join("")}</ul>
          </section>
          <section class="card"><h2>Top brokers</h2>
            <ul class="toplist">${brokers.slice(0, 12).map((b) => `<li><a href="#/b/${enc(b.b)}"><span class="nm">${esc(b.b)}</span><span class="n">${num(b.n)}</span></a></li>`).join("")}
            <li><a href="#/brokers"><span class="nm">All ${brokers.length} brokers →</span></a></li></ul>
          </section>
          <section class="card"><h2>Sources scanned</h2>
            <ul class="toplist">${srcRows.map(([s, n]) => `<li><a href="#/all"><span class="nm">${esc(m.sources[s] || s)}</span><span class="n">${num(n)}</span></a></li>`).join("")}</ul>
          </section>
        </aside>
      </div>`;
    listView($("#latest"), R, { showStock: true });
  }

  function consensus(list) {
    const latest = new Map(); // broker -> latest report with rating or target
    for (const r of list) {
      if (!(r.rb || r.tp)) continue;
      const p = latest.get(r.b);
      if (!p || r.d > p.d) latest.set(r.b, r);
    }
    const calls = [...latest.values()];
    const cut = daysAgo(180);
    const fresh = calls.filter((r) => r.d >= cut);
    const tps = fresh.filter((r) => r.tp).map((r) => r.tp);
    const counts = { pos: 0, neu: 0, neg: 0 };
    for (const r of fresh) if (r.rb) counts[r.rb]++;
    const lastPrice = list.find((r) => r.pr);
    return { calls, fresh, tps, counts, lastPrice };
  }

  function chartSVG(list) {
    const pts = list.filter((r) => r.tp || r.pr);
    if (pts.length < 2) return "";
    // draw at the real on-screen width so axis labels stay legible on phones
    const W = Math.round(Math.min(900, Math.max(320, view.clientWidth - 72)));
    const H = W < 600 ? 200 : 230, L = 56, Rr = 12, T = 12, B = 26;
    const x0 = +new Date("2026-01-01"), x1 = Date.now();
    const vals = pts.flatMap((r) => [r.tp, r.pr].filter(Boolean));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || hi * 0.05;
    lo -= pad; hi += pad;
    const X = (d) => L + ((+new Date(d) - x0) / (x1 - x0)) * (W - L - Rr);
    const Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
    const col = { pos: "var(--pos)", neu: "var(--neu)", neg: "var(--neg)" };
    let g = "";
    for (let i = 0; i <= 4; i++) {
      const v = lo + ((hi - lo) * i) / 4, y = Y(v);
      g += `<line class="ax" x1="${L}" x2="${W - Rr}" y1="${y}" y2="${y}"/><text x="${L - 8}" y="${y + 4}" text-anchor="end">${esc(inr(v))}</text>`;
    }
    for (let mth = 0; mth < 12; mth += W < 600 ? 2 : 1) {
      const d = `2026-${String(mth + 1).padStart(2, "0")}-01`;
      if (d > today) break;
      g += `<text x="${X(d)}" y="${H - 6}" text-anchor="start">${MON[mth]}</text>`;
    }
    const pr = pts.filter((r) => r.pr).sort((a, b) => (a.d < b.d ? -1 : 1));
    const path = pr.map((r, i) => `${i ? "L" : "M"}${X(r.d).toFixed(1)},${Y(r.pr).toFixed(1)}`).join("");
    const dots = pts.filter((r) => r.tp).map((r) =>
      `<circle cx="${X(r.d).toFixed(1)}" cy="${Y(r.tp).toFixed(1)}" r="5" fill="${col[r.rb] || "var(--ink-3)"}" fill-opacity=".85" stroke="var(--surface)" stroke-width="1.5" data-tip="${esc(`${fmtD(r.d)} · ${r.b} · ${r.ra || "—"} · target ${inr(r.tp)}`)}"/>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Broker target prices over 2026">
      ${g}${path ? `<path d="${path}" fill="none" stroke="var(--ink-3)" stroke-width="1.5" stroke-dasharray="3 3"/>` : ""}${dots}</svg>`;
  }

  function stockPage(k) {
    setNav("");
    const list = (byKey.get(k) || []).slice().sort((a, b) => (a.d < b.d ? 1 : -1));
    if (!list.length) { view.innerHTML = `<div class="empty">No 2026 reports found for “${esc(k)}”. <a href="#/">Back to search</a></div>`; return; }
    const sym = k.startsWith("~") ? null : k;
    const name = prettyName(nameOf.get(k));
    const ind = sym && S[sym] ? S[sym][1] : null;
    const c = consensus(list);
    const tot = c.counts.pos + c.counts.neu + c.counts.neg;
    const med = median(c.tps);
    const ref = c.lastPrice ? c.lastPrice.pr : null;
    const up = med && ref ? (med / ref - 1) * 100 : null;
    const pdfs = list.filter(hasPdf).length;
    const links = sym ? `
      <a class="btn" href="https://www.screener.in/company/${enc(sym)}/" target="_blank" rel="noopener noreferrer">${ICON.ext}Screener</a>
      <a class="btn" href="https://www.nseindia.com/get-quotes/equity?symbol=${enc(sym)}" target="_blank" rel="noopener noreferrer">${ICON.ext}NSE</a>` : "";
    const chart = chartSVG(list);
    view.innerHTML = `
      <div class="crumbs"><a href="#/">Home</a> / Stock</div>
      <div class="sh">
        <h1>${esc(name)}</h1>${sym ? `<span class="tick">${esc(sym)}</span>` : `<span class="tick">not NSE-listed</span>`}
        ${ind ? `<span class="ind">${esc(ind)}</span>` : ""}
        <div class="links">${links}</div>
      </div>
      <section class="card cons">
        <div><div class="lab">Reports in 2026</div><div class="val">${list.length}</div><div class="sub">${new Set(list.map((r) => r.b)).size} brokers · ${pdfs} PDF${pdfs === 1 ? "" : "s"}${PUB ? " linked" : " saved"} · latest ${fmtD(list[0].d)}</div></div>
        <div><div class="lab">Latest rating per broker (180 days)</div>
          ${tot ? `<div class="split"><i class="p" style="width:${(c.counts.pos / tot) * 100}%"></i><i class="u" style="width:${(c.counts.neu / tot) * 100}%"></i><i class="n" style="width:${(c.counts.neg / tot) * 100}%"></i></div>
          <div class="legend"><span><b>${c.counts.pos}</b> buy</span><span><b>${c.counts.neu}</b> hold</span><span><b>${c.counts.neg}</b> sell</span></div>` : `<div class="sub">No ratings published</div>`}
        </div>
        <div><div class="lab">Median target (latest per broker)</div><div class="val">${med ? inr(med) : "–"}</div><div class="sub">${c.tps.length ? `range ${inr(Math.min(...c.tps))} – ${inr(Math.max(...c.tps))} · ${c.tps.length} targets` : "No targets in the last 180 days"}</div></div>
        <div><div class="lab">Implied move</div><div class="val" style="color:${up == null ? "inherit" : up >= 0 ? "var(--pos)" : "var(--neg)"}">${up == null ? "–" : pct(up)}</div><div class="sub">${ref ? `vs ${inr(ref)}, price at the latest call (${fmtD(c.lastPrice.d)})` : "No reference price"}</div></div>
      </section>
      ${chart ? `<section class="card" style="margin-bottom:20px"><h2>Target prices through 2026 <span style="text-transform:none;letter-spacing:0;font-weight:400">· dots = broker targets coloured by rating, dashed = price when each call was made</span></h2><div class="chartwrap">${chart}</div></section>` : ""}
      <section class="card"><h2>All reports on ${esc(name)}</h2><div id="slist"></div></section>`;
    listView($("#slist"), list, { showStock: false });
    wireTips();
  }

  function brokerPage(b) {
    setNav("#/brokers");
    const list = byBroker.get(b) || [];
    view.innerHTML = `
      <div class="crumbs"><a href="#/">Home</a> / <a href="#/brokers">Brokers</a></div>
      <div class="sh"><h1>${esc(b)}</h1><span class="ind">${num(list.length)} reports in 2026 · ${new Set(list.map(stockKey).filter(Boolean)).size} stocks</span></div>
      <section class="card"><div id="blist"></div></section>`;
    listView($("#blist"), list, { showStock: true, noBroker: true });
  }

  function brokersPage() {
    setNav("#/brokers");
    view.innerHTML = `
      <div class="sh"><h1>Brokers &amp; research houses</h1><span class="ind">${brokers.length} publishers</span></div>
      <section class="card" style="padding-top:16px"><div class="blist">${brokers.map((b) => `<a href="#/b/${enc(b.b)}"><span>${esc(b.b)}</span><span class="n">${num(b.n)}</span></a>`).join("")}</div></section>`;
  }

  function allPage(params) {
    setNav("#/all");
    view.innerHTML = `
      <div class="sh"><h1>All reports</h1><span class="ind">${num(R.length)} reports since ${fmtD(D.meta.min_date)}</span></div>
      <section class="card"><div id="alist"></div></section>`;
    const state = { q: params.get("q") || "", b: params.get("b") || "", r: params.get("r") || "", pdf: params.get("pdf") === "1", days: params.get("days") || "" };
    listView($("#alist"), R, {
      showStock: true, state,
      onState: (s) => {
        const p = new URLSearchParams();
        for (const [k, v] of Object.entries(s)) if (v) p.set(k, v === true ? "1" : v);
        const h = "#/all" + (p.toString() ? "?" + p : "");
        if (location.hash !== h) history.replaceState(null, "", h);
      },
    });
    if (state.q) qi.value = state.q;
  }

  /* ---------- tooltips for chart ---------- */
  let tip;
  function wireTips() {
    tip ||= Object.assign(document.createElement("div"), { className: "tip", hidden: true });
    document.body.appendChild(tip);
    view.querySelectorAll("[data-tip]").forEach((el) => {
      el.addEventListener("mouseenter", () => { tip.textContent = el.dataset.tip; tip.hidden = false; });
      el.addEventListener("mousemove", (e) => { tip.style.left = Math.min(e.clientX + 12, innerWidth - 290) + "px"; tip.style.top = e.clientY + 14 + "px"; });
      el.addEventListener("mouseleave", () => { tip.hidden = true; });
    });
  }

  /* ---------- router ---------- */
  function route() {
    const h = location.hash.slice(1) || "/";
    const [path, qs] = h.split("?");
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    if (tip) tip.hidden = true;
    ac.hidden = true;
    if (parts[0] === "s" && parts[1]) stockPage(parts.slice(1).join("/"));
    else if (parts[0] === "b" && parts[1]) brokerPage(parts.slice(1).join("/"));
    else if (parts[0] === "brokers") brokersPage();
    else if (parts[0] === "all") allPage(new URLSearchParams(qs || ""));
    else home();
    if (parts[0] !== "all") qi.value = "";
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);

  const m = D.meta || {};
  if (PUB) {
    $("#foot-meta").innerHTML = `Updated ${fmtD((m.generated || "").slice(0, 10))} · ${num(R.length)} reports dated ${fmtD(m.min_date)} or later` +
      (safeUrl(m.repo) ? ` · <a href="${esc(m.repo)}" rel="noopener">Source code on GitHub</a>` : "");
    $("#foot-note").textContent = "This site indexes research that brokers have published publicly and links to the originals. " +
      "It makes no recommendations of its own. Reports and their contents belong to their publishers. Nothing here is investment advice.";
  } else {
    $("#foot-meta").textContent = `Built ${m.generated || "?"} · ${num(R.length)} reports dated ${fmtD(m.min_date)} or later · run update.bat to refresh.`;
  }
  route();
})();
