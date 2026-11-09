/* Product areas: finer-grained spending lines for the selected region.
   Independent of app.js. It listens for the "dash:render" event and never
   changes the rest of the page. If data/detail.json is missing the card stays hidden. */
(() => {
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 1) => (v == null || Number.isNaN(v) ? "–" : v.toFixed(d));
const signed = (v, d = 1) => { if (v == null) return "–"; const r = +v.toFixed(d); return (r > 0 ? "+" : r < 0 ? "−" : "") + Math.abs(r).toFixed(d); };
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const COUNTRY = { US: "US", CA: "Canadian" };

const SMALL = 0.25;   // areas under this share of the budget are measured with more noise
const ui = { group: "all", sort: "growth", sel: null };
let DET = null, loading = false, last = null, wired = false;
const series = new Map();   // area id -> Map(region code -> [[year, share, nominal, real], ...])
const areaById = new Map();
const avgCache = new Map();

function ingest(d) {
  DET = d;
  for (const a of d.areas) { areaById.set(a.id, a); series.set(a.id, new Map()); }
  for (const [ai, ri, y, share, nom, real] of d.rows) {
    const m = series.get(d.areas[ai].id), code = d.region_codes[ri];
    if (!m.has(code)) m.set(code, []);
    m.get(code).push([y, share, nom, real]);
  }
  for (const m of series.values()) for (const arr of m.values()) arr.sort((p, q) => p[0] - q[0]);
}

/* ---------- numbers ---------- */
const spendOf = (p, real) => (p ? (real ? p[3] : p[2]) : null);
const atOrBefore = (arr, y) => { let out = null; for (const p of arr) { if (p[0] <= y) out = p; else break; } return out; };
const exact = (arr, y) => arr.find((p) => p[0] === y) || null;

function countryAvg(area, country, y) {
  const k = area + "|" + country + "|" + y;
  if (avgCache.has(k)) return avgCache.get(k);
  let s = 0, n = 0;
  for (const [code, arr] of series.get(area)) {
    if (!code.startsWith(country)) continue;
    const p = exact(arr, y);
    if (p) { s += p[1]; n++; }
  }
  const out = n ? s / n : null;
  avgCache.set(k, out);
  return out;
}

function statsFor(area, region, country, yr, real) {
  const arr = series.get(area).get(region);
  if (!arr) return null;
  const p = atOrBefore(arr, yr == null ? 9999 : yr);
  if (!p) return null;
  const avg = countryAvg(area, country, p[0]);
  let prev = null, gap = 0;
  for (const g of [5, 4, 6]) { const q = exact(arr, p[0] - g); if (q) { prev = q; gap = g; break; } }
  let rel = null, growth = null;
  if (prev && prev[1] > 0) rel = ((p[1] / prev[1]) ** (5 / gap) - 1) * 100;
  const v1 = spendOf(p, real), v0 = spendOf(prev, real);
  if (prev && v0 > 0 && v1 > 0) growth = ((v1 / v0) ** (1 / gap) - 1) * 100;
  // rank among regions of this country in the same year
  const all = [];
  for (const [code, a2] of series.get(area)) {
    if (!code.startsWith(country)) continue;
    const q = exact(a2, p[0]);
    if (q) all.push([code, q[1]]);
  }
  all.sort((a, b) => b[1] - a[1]);
  return { year: p[0], share: p[1], index: avg ? (p[1] / avg) * 100 : null, rel, growth, gap,
           rank: all.findIndex((x) => x[0] === region) + 1, of: all.length, avg, all };
}

const signal = (s) => (s.growth == null || s.rel == null ? "" : s.growth > 0 && s.rel > 0 ? "Rising" : s.growth < 0 && s.rel < 0 ? "Falling" : "Mixed");

/* ---------- drawing ---------- */
function groupLabel(id, cats) { const c = cats.find((x) => x.id === id); return c ? c.label : id; }

function sparkline(area, region, country, real, W) {
  const arr = series.get(area).get(region);
  if (!arr || arr.length < 2) return "";
  const H = 150, L = 46, R = 48, T = 10, B = 24;
  const ys = arr.map((p) => p[0]);
  const reg = arr.map((p) => p[1]);
  const avg = ys.map((y) => countryAvg(area, country, y));
  const all = reg.concat(avg.filter((v) => v != null));
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.12 || hi * 0.1 || 0.1; lo = Math.max(0, lo - pad); hi += pad;
  const x = (y) => L + ((y - ys[0]) / (ys[ys.length - 1] - ys[0] || 1)) * (W - L - R);
  const yv = (v) => T + (1 - (v - lo) / (hi - lo || 1)) * (H - T - B);
  const path = (vals) => { let d = "", pen = false; vals.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + x(ys[i]).toFixed(1) + "," + yv(v).toFixed(1); pen = true; }); return d; };
  const grid = [lo, (lo + hi) / 2, hi].map((v) => `<line x1="${L}" x2="${W - R}" y1="${yv(v)}" y2="${yv(v)}" stroke="${cssv("--grid")}"/><text x="${L - 6}" y="${yv(v) + 4}" text-anchor="end">${v.toFixed(2)}%</text>`).join("");
  const dots = reg.length < 8 ? arr.map((p) => `<circle cx="${x(p[0])}" cy="${yv(p[1])}" r="3" fill="${cssv("--s1")}"/>`).join("") : "";
  const endX = x(ys[ys.length - 1]);
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Share of budget over time, region versus country average">
    ${grid}
    <path d="${path(avg)}" fill="none" stroke="${cssv("--muted")}" stroke-width="1.6" stroke-dasharray="5 4"/>
    <path d="${path(reg)}" fill="none" stroke="${cssv("--s1")}" stroke-width="2.2"/>${dots}
    <text x="${L}" y="${H - 6}">${ys[0]}</text><text x="${W - R}" y="${H - 6}" text-anchor="end">${ys[ys.length - 1]}</text>
    <text x="${endX + 5}" y="${yv(reg[reg.length - 1]) + 4}" class="lbl">${reg[reg.length - 1].toFixed(2)}%</text>
  </svg>`;
}

function render(ctx) {
  const card = $("#detail-card");
  if (!card || !DET || !ctx || !ctx.region) return;
  const reg = ctx.regions.find((r) => r.code === ctx.region);
  if (!reg) return;
  const country = reg.country;
  const real = !!ctx.real;
  avgCache.clear();

  const list = [];
  for (const a of DET.areas) {
    if (!a.countries.includes(country)) continue;
    const s = statsFor(a.id, ctx.region, country, ctx.year, real);
    if (s) list.push({ a, s });
  }
  if (!list.length) { card.hidden = false; $("#det-body").innerHTML = `<p class="hint">No product-area detail for ${esc(reg.name)}.</p>`; return; }
  card.hidden = false;

  const yearUsed = Math.max(...list.map((x) => x.s.year));
  $("#det-h").textContent = `Product areas in ${reg.name}`;
  $("#det-hint").textContent =
    `Finer spending lines inside the eight categories, for ${yearUsed}. Index compares ${reg.name} with the average ` +
    `${COUNTRY[country]} region (100 = average). Share change is the relative change in an area's share of the budget over about ` +
    `five years, and growth is real spend a year${real ? "" : " (not adjusted for inflation, since you picked nominal dollars)"}. ` +
    `Areas under ${SMALL}% of the budget are tagged "Small base": the survey measures them with more noise, so treat their swings as leads to check, not trends. ` +
    `Click a row for the trend and the regions that spend most.`;

  // group filter options (only groups present)
  const groups = [...new Set(DET.areas.filter((a) => a.countries.includes(country)).map((a) => a.group))];
  const gSel = $("#d-group");
  const wantG = groups.includes(ui.group) ? ui.group : "all";
  ui.group = wantG;
  gSel.innerHTML = `<option value="all">All categories</option>` +
    groups.map((g) => `<option value="${esc(g)}">${esc(groupLabel(g, ctx.cats))}</option>`).join("");
  gSel.value = ui.group;
  $("#d-sort").value = ui.sort;

  // plain-English lead
  const solid = list.filter((x) => x.s.share >= SMALL);
  const topG = solid.filter((x) => x.s.growth != null).sort((p, q) => q.s.growth - p.s.growth).slice(0, 3);
  const topI = solid.filter((x) => x.s.index != null).sort((p, q) => q.s.index - p.s.index).slice(0, 3);
  const parts = [];
  if (topG.length) parts.push(`Fastest real spending growth: ${topG.map((x) => `<b>${esc(x.a.label)}</b> (${signed(x.s.growth)}% a year)`).join(", ")}.`);
  if (topI.length) parts.push(`Where ${esc(reg.name)} spends most compared with the ${COUNTRY[country]} average: ${topI.map((x) => `<b>${esc(x.a.label)}</b> (index ${Math.round(x.s.index)})`).join(", ")}.`);
  $("#det-lead").innerHTML = parts.map((p) => `<p>${p}</p>`).join("");

  // table
  const shown = list.filter((x) => ui.group === "all" || x.a.group === ui.group);
  const key = { growth: (x) => x.s.growth, shift: (x) => x.s.rel, index: (x) => x.s.index, share: (x) => x.s.share }[ui.sort];
  const thin = (x) => x.s.share < SMALL;
  shown.sort((p, q) => {
    if ((ui.sort === "growth" || ui.sort === "shift") && thin(p) !== thin(q)) return thin(p) ? 1 : -1;
    const a = key(p), b = key(q); if (a == null) return 1; if (b == null) return -1; return b - a; });
  const cls = (v) => (v == null || Math.abs(v) < 0.05 ? "" : v > 0 ? "pos" : "neg");
  const body = shown.map(({ a, s }) => {
    const small = s.share < SMALL;
    const sig = small ? "Small base" : signal(s);
    const sigCls = small ? "small" : sig.toLowerCase();
    const sub = a.part_of && areaById.get(a.part_of) ? `<span class="sub2">part of ${esc(areaById.get(a.part_of).label)}</span>` : "";
    return `<tr data-area="${esc(a.id)}" tabindex="0" class="${ui.sel === a.id ? "sel" : ""}">
      <td>${esc(a.label)}${sub}</td>
      <td class="hide-s">${esc(groupLabel(a.group, ctx.cats))}</td>
      <td class="n">${num(s.share, 2)}%</td>
      <td class="n">${s.index == null ? "–" : Math.round(s.index)}</td>
      <td class="n ${cls(s.rel)}">${s.rel == null ? "–" : signed(s.rel, 0) + "%"}</td>
      <td class="n ${cls(s.growth)}">${s.growth == null ? "–" : signed(s.growth, 1) + "%"}</td>
      <td class="n"><span class="badge ${sigCls}"${small ? ' title="Under 0.25% of the budget. Survey estimates this small are noisy, so big swings may be sampling noise."' : ""}>${sig || "–"}</span></td></tr>`;
  }).join("");
  $("#det-body").innerHTML = `<table><thead><tr>
      <th>Product area</th><th class="hide-s">Category</th><th class="n">Share of budget</th><th class="n">Index</th>
      <th class="n">5-yr share change</th><th class="n">Real growth a year</th><th class="n">Signal</th></tr></thead>
      <tbody>${body || `<tr><td colspan="7">Nothing in this category.</td></tr>`}</tbody></table>`;

  // focus panel
  const focus = $("#det-focus");
  const cur = ui.sel && list.find((x) => x.a.id === ui.sel);
  if (!cur) { focus.innerHTML = ""; return; }
  const { a, s } = cur;
  const top = s.all.slice(0, 5).map(([code, sh]) => {
    const r = ctx.regions.find((x) => x.code === code);
    return `<li${code === ctx.region ? ' class="me"' : ""}><span>${esc(r ? r.name : code)}</span><span>${num(sh, 2)}% · index ${s.avg ? Math.round((sh / s.avg) * 100) : "–"}</span></li>`;
  }).join("");
  focus.innerHTML = `<div class="focus">
    <h3>${esc(a.label)} in ${esc(reg.name)}</h3>
    <p class="hint">Share of budget: ${esc(reg.name)} (solid) vs ${COUNTRY[country]} average (dashed). ${esc(reg.name)} ranks ${s.rank} of ${s.of} for this area in ${s.year}.</p>
    <div class="chart spark"></div>
    <h4>Biggest spenders, ${s.year}</h4><ol class="toplist">${top}</ol>
    ${a.note ? `<p class="hint">${esc(a.note)}</p>` : ""}
    <p class="hint">${country === "US" ? "BEA lines cover all spending, including what insurers and governments pay." : "Statistics Canada lines are what households report spending themselves."} Compare regions within a country, not across the border.</p>
  </div>`;
  const box = focus.querySelector(".spark");
  box.innerHTML = sparkline(a.id, ctx.region, country, real, Math.max(260, Math.floor(box.clientWidth)));
  if (ui.justPicked) { ui.justPicked = false; focus.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
}

/* ---------- wiring ---------- */
function wire() {
  if (wired) return; wired = true;
  $("#d-group").addEventListener("change", (e) => { ui.group = e.target.value; render(last); });
  $("#d-sort").addEventListener("change", (e) => { ui.sort = e.target.value; render(last); });
  const pick = (e) => { const r = e.target.closest("[data-area]"); if (r) { ui.sel = ui.sel === r.dataset.area ? null : r.dataset.area; ui.justPicked = !!ui.sel; render(last); } };
  $("#det-body").addEventListener("click", pick);
  $("#det-body").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(e); } });
}

function handle(ctx) {
  last = ctx;
  if (DET) { render(ctx); return; }
  if (loading) return;
  loading = true;
  fetch("data/detail.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((d) => { ingest(d); wire(); render(last); })
    .catch(() => { /* no detail file: the card stays hidden */ });
}

window.addEventListener("dash:render", (e) => handle(e.detail));
if (window.__dashLast) handle(window.__dashLast);
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => last && render(last));
let lastW = 0;
addEventListener("resize", () => { const b = document.querySelector(".spark"); if (b && Math.abs(b.clientWidth - lastW) >= 8) { lastW = b.clientWidth; ui.justPicked = false; render(last); } });
})();