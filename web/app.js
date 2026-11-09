(() => {
"use strict";

const $ = (s) => document.querySelector(s);
const state = { cat: "recreation", metric: "index", bench: "all", real: true,
                year: null, region: null, trend: "share" };
let D, years = [], regionsByCode = new Map();
const rows = new Map();
const benchCache = new Map();

const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const num = (v, d = 1) => (v == null || Number.isNaN(v) ? "–" : v.toFixed(d));
const signed = (v, d = 1) => (v == null ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d));
const catLabel = (id) => D.categories.find((c) => c.id === id).label;

/* ---------- data access ---------- */
const get = (reg, cat, y) => rows.get(reg + "|" + cat + "|" + y);
const spend = (r) => (r ? (state.real ? r.real : r.nominal) : null);
const countryOf = (code) => regionsByCode.get(code).country;

function bench(cat, y, country) {
  const k = cat + "|" + y + "|" + country;
  if (benchCache.has(k)) return benchCache.get(k);
  let s = 0, n = 0;
  for (const r of D.regions) {
    if (country && r.country !== country) continue;
    const v = get(r.code, cat, y);
    if (v) { s += v.share; n++; }
  }
  const out = n ? s / n : null;
  benchCache.set(k, out);
  return out;
}
const benchFor = (code, cat, y) => bench(cat, y, state.bench === "country" ? countryOf(code) : "");

function countryAvgSpend(cat, y, country) {
  let s = 0, n = 0;
  for (const r of D.regions) {
    if (r.country !== country) continue;
    const v = spend(get(r.code, cat, y));
    if (v != null) { s += v; n++; }
  }
  return n ? s / n : null;
}

const METRICS = {
  index:  { label: "Index vs average (100 = average)", kind: "div", center: 100, fmt: (v) => String(Math.round(v)), long: (v) => num(v, 0) },
  share:  { label: "Share of budget", kind: "seq", fmt: (v) => num(v, 1), long: (v) => num(v, 1) + "%" },
  dshare: { label: "5-yr change in share (points)", kind: "div", center: 0, fmt: (v) => signed(v, 1), long: (v) => signed(v, 1) + " pts" },
  growth: { label: "5-yr spend growth (% a year)", kind: "div", center: 0, fmt: (v) => signed(v, 1), long: (v) => signed(v, 1) + "% a year" },
};

function metricVal(code, cat = state.cat, y = state.year, metric = state.metric) {
  const r = get(code, cat, y);
  if (!r) return null;
  if (metric === "share") return r.share;
  if (metric === "index") {
    const b = benchFor(code, cat, y);
    return b ? (r.share / b) * 100 : null;
  }
  const p = get(code, cat, y - 5);
  if (!p) return null;
  if (metric === "dshare") return r.share - p.share;
  const a = spend(r), b = spend(p);
  return a != null && b ? (Math.pow(a / b, 1 / 5) - 1) * 100 : null;
}

/* ---------- colour ---------- */
function hex(c) {
  const h = c.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
function mix(a, b, t) {
  const A = hex(a), B = hex(b);
  return "#" + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
function lum(c) {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const [r, g, b] = hex(c).map(f);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const textOn = (bg) => (lum(bg) > 0.3 ? "#0b0b0b" : "#ffffff");

function colorScale(kind, vals, center) {
  if (kind === "div") {
    const neutral = cssv("--neutral"), pos = cssv("--pos"), neg = cssv("--neg");
    const dev = vals.map((v) => Math.abs(v - center)).sort((a, b) => a - b);
    let m = dev.length ? dev[Math.min(dev.length - 1, Math.floor(dev.length * 0.95))] : 1;
    m = m || 1;
    return {
      domain: [center - m, center + m], center,
      color: (v) => v >= center ? mix(neutral, pos, Math.min(1, (v - center) / m))
                                : mix(neutral, neg, Math.min(1, (center - v) / m)),
    };
  }
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const a = cssv("--seq-lo"), b = cssv("--seq-hi");
  return { domain: [lo, hi], color: (v) => mix(a, b, hi > lo ? (v - lo) / (hi - lo) : 0.5) };
}

/* ---------- map ---------- */
const TILE = 58, GAP = 4;
const GRIDS = [{ id: "US", title: "United States" }, { id: "CA", title: "Canada" }];

function renderMap() {
  const M = METRICS[state.metric];
  const vals = D.regions.map((r) => metricVal(r.code)).filter((v) => v != null);
  const sc = vals.length ? colorScale(M.kind, vals, M.center) : null;
  let html = "";
  const maxCols = Math.max(...D.regions.map((r) => r.col)) + 1;
  // Phone width: tiles get small, so show a big state code only. The value is in
  // the selected-region readout above the map (tap a tile to update it).
  const cmp = matchMedia("(max-width: 640px)").matches;
  const tileText = (x, y, code, fillAttr, val) => cmp
    ? `<text class="tc big" x="${x + TILE / 2}" y="${y + TILE / 2 + 8}" text-anchor="middle"${fillAttr}>${code}</text>`
    : `<text class="tc" x="${x + TILE / 2}" y="${y + 29}" text-anchor="middle"${fillAttr}>${code}</text>` +
      `<text class="tv" x="${x + TILE / 2}" y="${y + 44}" text-anchor="middle"${fillAttr}>${val}</text>`;
  for (const g of GRIDS) {
    const regs = D.regions.filter((r) => r.country === g.id);
    const cols = Math.max(...regs.map((r) => r.col)) + 1, rws = Math.max(...regs.map((r) => r.row)) + 1;
    const W = cols * (TILE + GAP), H = rws * (TILE + GAP);
    let t = "";
    for (const r of regs) {
      const v = metricVal(r.code);
      const x = r.col * (TILE + GAP), y = r.row * (TILE + GAP);
      const short = r.code.split("-")[1];
      const sel = r.code === state.region ? " sel" : "";
      if (v == null || !sc) {
        t += `<g class="tile na${sel}" data-code="${r.code}" tabindex="0" role="button" aria-label="${esc(r.name)}: no data">` +
             `<rect x="${x}" y="${y}" width="${TILE}" height="${TILE}" rx="7"/>` +
             tileText(x, y, short, "", "n/a") + `</g>`;
        continue;
      }
      const fill = sc.color(v), ink = textOn(fill);
      t += `<g class="tile${sel}" data-code="${r.code}" tabindex="0" role="button" aria-label="${esc(r.name)}: ${esc(M.long(v))}">` +
           `<rect x="${x}" y="${y}" width="${TILE}" height="${TILE}" rx="7" fill="${fill}"/>` +
           tileText(x, y, short, ` fill="${ink}"`, M.fmt(v)) + `</g>`;
    }
    const widthPct = (cols / maxCols) * 100;  // keep tile size equal across grids
    html += `<div class="grid-title">${g.title}</div><svg viewBox="0 0 ${W} ${H}" style="width:${widthPct}%" role="group" aria-label="${g.title} tile map">${t}</svg>`;
  }
  $("#maps").innerHTML = html;

  $("#map-h").textContent = `${catLabel(state.cat)}: ${M.label.toLowerCase()}, ${state.year}`;
  $("#map-hint").textContent = state.metric === "index"
    ? `Blue = households spend a bigger share here than the ${state.bench === "all" ? "North American" : "country"} average; red = smaller. Click a tile for detail.`
    : "Click a tile for detail. Grey tiles have no data.";

  if (sc) {
    const [lo, hi] = sc.domain;
    const stops = M.kind === "div"
      ? `${sc.color(lo)}, ${sc.color(sc.center)}, ${sc.color(hi)}` : `${sc.color(lo)}, ${sc.color(hi)}`;
    $("#legend").innerHTML = `<div class="bar" style="background:linear-gradient(to right, ${stops})"></div>` +
      `<div class="labels"><span>${M.long(lo)}</span>` +
      (M.kind === "div" ? `<span>${M.long(sc.center)}</span>` : "") + `<span>${M.long(hi)}</span></div>`;
  } else {
    $("#legend").innerHTML = "";
  }
}

/* ---------- selected-region readout (works on touch, where there is no hover) ---------- */
function renderSel() {
  const code = state.region, reg = regionsByCode.get(code), a = get(code, state.cat, state.year);
  const el = $("#sel");
  if (!a) { el.innerHTML = `<b>${esc(reg.name)}</b><span>No data for ${state.year}</span>`; return; }
  const M = METRICS[state.metric], v = metricVal(code), idx = metricVal(code, state.cat, state.year, "index");
  el.innerHTML = `<b>${esc(reg.name)}</b><span>${esc(M.label)}: ${v == null ? "n/a" : M.long(v)}` +
    ` · Share of budget ${num(a.share, 1)}% · Index ${idx == null ? "n/a" : Math.round(idx)}</span>`;
}

/* ---------- region panel ---------- */
function renderRegion() {
  const code = state.region, reg = regionsByCode.get(code);
  const u = D.units[reg.country];
  $("#reg-h").textContent = `${reg.name}: where it over-indexes (${state.year})`;
  $("#reg-hint").textContent = `Share of budget vs the ${state.bench === "all" ? "North American" : reg.country === "US" ? "US" : "Canadian"} average of regions (100 = average). Click a bar to focus that category.`;
  const items = D.categories.map((c) => {
    const r = get(code, c.id, state.year), b = benchFor(code, c.id, state.year);
    return { id: c.id, label: c.label, idx: r && b ? (r.share / b) * 100 : null };
  }).filter((i) => i.idx != null).sort((a, b) => b.idx - a.idx);
  if (!items.length) { $("#bars").innerHTML = `<p class="hint">No data for ${esc(reg.name)} in ${state.year}.</p>`; return; }
  const maxDev = Math.max(20, ...items.map((i) => Math.abs(i.idx - 100)));
  $("#bars").innerHTML = items.map((i) => {
    const w = (Math.abs(i.idx - 100) / maxDev) * 50;
    const over = i.idx >= 100;
    const style = over ? `left:50%;width:${w}%;background:var(--pos);border-radius:0 4px 4px 0`
                       : `right:50%;width:${w}%;background:var(--neg);border-radius:4px 0 0 4px`;
    return `<div class="barrow${i.id === state.cat ? " sel" : ""}" data-cat="${i.id}" tabindex="0" role="button" aria-label="${esc(i.label)}: index ${Math.round(i.idx)}">` +
           `<span>${esc(i.label)}</span><span class="track"><span class="fill" style="${style}"></span></span>` +
           `<span class="num">${Math.round(i.idx)}</span></div>`;
  }).join("") + `<p class="hint" style="margin-top:8px">Spend basis: ${u.currency} ${u.basis}.</p>`;
}

/* ---------- trend chart ---------- */
function renderTrend() {
  const code = state.region, reg = regionsByCode.get(code), cat = state.cat;
  const mode = state.trend;
  const u = D.units[reg.country];
  const benchCountry = state.bench === "country" ? reg.country : "";
  const regVal = (y) => { const r = get(code, cat, y); return r ? (mode === "share" ? r.share : spend(r)) : null; };
  const benVal = (y) => mode === "share" ? bench(cat, y, benchCountry) : countryAvgSpend(cat, y, reg.country);
  const benchName = mode === "share"
    ? (benchCountry ? `${reg.country === "US" ? "US" : "Canada"} average` : "North America average")
    : `${reg.country === "US" ? "US" : "Canada"} average`;
  const dollars = state.real ? `constant ${D.meta.base_year[reg.country] || ""} ${u.currency}` : `nominal ${u.currency}`;
  $("#tr-h").textContent = `${catLabel(cat)} in ${reg.name}`;
  $("#tr-legend").innerHTML = `<span><i style="border-color:var(--s1)"></i>${esc(reg.name)}</span>` +
    `<span><i class="dash" style="border-color:var(--muted)"></i>${benchName}</span>` +
    `<span>${mode === "share" ? "Share of budget (%)" : `${u.basis}, ${dollars}`}</span>`;

  const A = years.map((y) => regVal(y)), B = years.map((y) => benVal(y));
  const all = A.concat(B).filter((v) => v != null);
  if (!all.length) { $("#trend").innerHTML = `<p class="hint">No data.</p>`; return; }
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo || 1) * 0.12; lo = Math.max(0, lo - pad); hi += pad;

  // Draw at the real pixel width so text stays 11px on a phone instead of shrinking.
  const cw = $("#trend").clientWidth || 640;
  const W = Math.max(280, Math.min(cw, 720));
  const narrow = W < 460;
  const H = Math.round(Math.max(230, Math.min(300, W * 0.58)));
  const L = narrow ? 42 : 50, R = narrow ? 44 : 70, T = 14, Bm = 28;
  const x = (y) => L + ((y - years[0]) / (years[years.length - 1] - years[0] || 1)) * (W - L - R);
  const yy = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - Bm);
  const step = (W - L - R) / Math.max(1, years.length - 1);
  const fmtY = (v) => mode === "share" ? v.toFixed(1) + "%" : (v >= 1000 ? Math.round(v / 1000 * 10) / 10 + "k" : Math.round(v));

  let g = "";
  for (let i = 0; i <= 4; i++) {
    const v = lo + ((hi - lo) * i) / 4, py = yy(v);
    g += `<line x1="${L}" x2="${W - R}" y1="${py}" y2="${py}" stroke="var(--grid)"/>` +
         `<text x="${L - 6}" y="${py + 4}" text-anchor="end">${fmtY(v)}</text>`;
  }
  // COVID band
  const [c0, c1] = D.meta.covid_years;
  if (years.includes(c0)) {
    g += `<rect x="${x(c0) - step / 2}" y="${T}" width="${x(c1) - x(c0) + step}" height="${H - T - Bm}" fill="var(--grid)" opacity=".55"/>` +
         `<text x="${(x(c0) + x(c1)) / 2}" y="${T + 11}" text-anchor="middle">COVID-19</text>`;
  }
  // methodology breaks
  for (const by of (D.meta.break_years[reg.country] || [])) {
    if (by > years[0] && by <= years[years.length - 1]) {
      g += `<line x1="${x(by) - step / 2}" x2="${x(by) - step / 2}" y1="${T}" y2="${H - Bm}" stroke="var(--muted)" stroke-dasharray="3 3"/>` +
           `<text x="${x(by) - step / 2 + 3}" y="${T + 22}">series break</text>`;
    }
  }
  const tickEvery = Math.max(1, Math.ceil(years.length / Math.max(2, Math.floor((W - L - R) / 46))));
  years.forEach((y, i) => { if ((years.length - 1 - i) % tickEvery === 0) g += `<text x="${x(y)}" y="${H - 8}" text-anchor="middle">${y}</text>`; });
  g += `<line x1="${L}" x2="${W - R}" y1="${H - Bm}" y2="${H - Bm}" stroke="var(--axis)"/>`;

  const path = (arr) => { let d = "", pen = false;
    arr.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + x(years[i]).toFixed(1) + " " + yy(v).toFixed(1); pen = true; });
    return d; };
  g += `<path d="${path(B)}" fill="none" stroke="var(--muted)" stroke-width="2" stroke-dasharray="5 4"/>`;
  g += `<path d="${path(A)}" fill="none" stroke="var(--s1)" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round"/>`;
  const last = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return [years[i], arr[i]]; return null; };
  const la = last(A), lb = last(B);
  if (la) g += `<text class="lbl" x="${x(la[0]) + 6}" y="${yy(la[1]) + (lb && Math.abs(yy(lb[1]) - yy(la[1])) < 12 && lb[1] > la[1] ? 10 : 4)}">${fmtY(la[1])}</text>`;
  if (lb) g += `<text class="lbl" x="${x(lb[0]) + 6}" y="${yy(lb[1]) + (la && Math.abs(yy(lb[1]) - yy(la[1])) < 12 && lb[1] > la[1] ? -2 : 4)}">${fmtY(lb[1])}</text>`;
  g += `<g id="xh" visibility="hidden"><line y1="${T}" y2="${H - Bm}" stroke="var(--axis)"/>` +
       `<circle id="xa" r="5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/>` +
       `<circle id="xb" r="4" fill="var(--muted)" stroke="var(--surface)" stroke-width="2"/></g>` +
       `<rect id="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - Bm}" fill="transparent" style="touch-action:pan-y"/>`;
  $("#trend").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Line chart of ${esc(catLabel(cat))} in ${esc(reg.name)} by year">${g}</svg>`;

  const svg = $("#trend svg"), hit = $("#hit"), xh = $("#xh"), tip = $("#tip");
  const move = (e) => {
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = 0, bd = Infinity;
    years.forEach((y, i) => { const d = Math.abs(x(y) - p.x); if (d < bd) { bd = d; best = i; } });
    const y = years[best];
    xh.setAttribute("visibility", "visible");
    xh.querySelector("line").setAttribute("x1", x(y)); xh.querySelector("line").setAttribute("x2", x(y));
    const set = (id, v) => { const c = $(id); if (v == null) c.setAttribute("visibility", "hidden"); else { c.setAttribute("visibility", "visible"); c.setAttribute("cx", x(y)); c.setAttribute("cy", yy(v)); } };
    set("#xa", A[best]); set("#xb", B[best]);
    const f = (v) => v == null ? "–" : mode === "share" ? v.toFixed(1) + "%" : Math.round(v).toLocaleString();
    tip.innerHTML = `<b>${y}</b><span>${esc(reg.name)}: ${f(A[best])}<br>${benchName}: ${f(B[best])}</span>`;
    showTip(e.clientX, e.clientY);
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);   // a plain tap on a phone
  hit.addEventListener("pointerleave", () => { xh.setAttribute("visibility", "hidden"); hideTip(); });
}

/* ---------- momentum + table ---------- */
function median(a) { if (!a.length) return null; a = a.slice().sort((p, q) => p - q); const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; }

function renderMomentum() {
  const y = state.year;
  const items = D.categories.map((c) => {
    const sh = [], dsh = [], gr = [];
    for (const r of D.regions) {
      const a = get(r.code, c.id, y); if (!a) continue;
      sh.push(a.share);
      const p = get(r.code, c.id, y - 5);
      if (p) {
        dsh.push(a.share - p.share);
        const s1 = spend(a), s0 = spend(p);
        if (s1 != null && s0) gr.push((Math.pow(s1 / s0, 1 / 5) - 1) * 100);
      }
    }
    const mean = (v) => v.length ? v.reduce((s, q) => s + q, 0) / v.length : null;
    return { id: c.id, label: c.label, share: mean(sh), dshare: mean(dsh), growth: median(gr) };
  }).sort((a, b) => (b.dshare ?? -99) - (a.dshare ?? -99));
  $("#momentum").innerHTML = `<div class="scroll"><table><thead><tr><th>Category</th><th class="n">Avg share of budget</th>` +
    `<th class="n">5-yr change (pts)</th><th class="n">Median real spend growth (% a year)</th></tr></thead><tbody>` +
    items.map((i) => `<tr data-cat="${i.id}" tabindex="0" class="${i.id === state.cat ? "sel" : ""}"><td>${esc(i.label)}</td>` +
      `<td class="n">${num(i.share, 1)}%</td><td class="n">${signed(i.dshare, 2)}</td><td class="n">${signed(i.growth, 1)}</td></tr>`).join("") +
    `</tbody></table></div>`;
}

function renderTable() {
  const list = D.regions.map((r) => ({ r, v: metricVal(r.code), a: get(r.code, state.cat, state.year) }))
    .filter((o) => o.a).sort((p, q) => (q.v ?? -1e9) - (p.v ?? -1e9));
  const M = METRICS[state.metric];
  $("#table").innerHTML = `<div class="tbl"><table><thead><tr><th>Region</th><th class="n">${esc(M.label)}</th><th class="n">Share of budget</th><th class="n">Spend</th></tr></thead><tbody>` +
    list.map(({ r, v, a }) => `<tr><td>${esc(r.name)} (${r.country})</td><td class="n">${v == null ? "–" : M.long(v)}</td><td class="n">${num(a.share, 1)}%</td>` +
      `<td class="n">${spend(a) == null ? "–" : Math.round(spend(a)).toLocaleString()} ${D.units[r.country].currency}</td></tr>`).join("") +
    `</tbody></table></div>`;
}

/* ---------- tooltip ---------- */
const tipEl = () => $("#tip");
function showTip(cx, cy) {
  const t = tipEl(); t.hidden = false;
  const w = t.offsetWidth, h = t.offsetHeight;
  let x = cx + 14, y = cy + 14;
  if (x + w > innerWidth - 8) x = cx - w - 14;
  if (y + h > innerHeight - 8) y = cy - h - 14;
  t.style.left = Math.max(8, x) + "px"; t.style.top = Math.max(8, y) + "px";
}
function hideTip() { tipEl().hidden = true; }

function tileTip(code, cx, cy) {
  const reg = regionsByCode.get(code), a = get(code, state.cat, state.year);
  const u = D.units[reg.country];
  if (!a) { tipEl().innerHTML = `<b>${esc(reg.name)}</b><span>No data for ${state.year}</span>`; showTip(cx, cy); return; }
  const idx = metricVal(code, state.cat, state.year, "index"), M = METRICS[state.metric], v = metricVal(code);
  tipEl().innerHTML = `<b>${esc(reg.name)}</b><span>${esc(catLabel(state.cat))}, ${state.year}<br>` +
    `${esc(M.label)}: ${v == null ? "n/a" : M.long(v)}<br>Share of budget: ${num(a.share, 1)}%<br>` +
    `Index: ${idx == null ? "n/a" : Math.round(idx)}<br>` +
    `Spend: ${spend(a) == null ? "n/a" : Math.round(spend(a)).toLocaleString() + " " + u.currency + " " + u.basis}</span>`;
  showTip(cx, cy);
}

/* ---------- orchestration ---------- */
function render() {
  benchCache.clear();
  $("#f-cat").value = state.cat;
  $("#f-region").value = state.region;
  renderMap(); renderSel(); renderRegion(); renderTrend(); renderMomentum(); renderTable();
  document.querySelectorAll("[data-trend]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.trend === state.trend)));
}

function init(data) {
  D = data;
  regionsByCode = new Map(D.regions.map((r) => [r.code, r]));
  const counts = new Map();
  for (const [reg, cat, y, share, nominal, real] of D.rows) {
    rows.set(reg + "|" + cat + "|" + y, { share, nominal, real });
    if (cat === D.categories[0].id) counts.set(y, (counts.get(y) || 0) + 1);
  }
  years = [...counts.keys()].sort((a, b) => a - b);
  const maxN = Math.max(...counts.values());
  state.year = [...years].reverse().find((y) => counts.get(y) >= 0.8 * maxN) || years[years.length - 1];
  const present = new Set(D.present);
  state.region = ["CA-ON", "US-CA"].find((c) => present.has(c)) || D.present[0];
  if (!D.categories.some((c) => c.id === state.cat)) state.cat = D.categories[0].id;

  $("#f-cat").innerHTML = D.categories.map((c) => `<option value="${c.id}">${esc(c.label)}</option>`).join("");
  const regOpts = (country, title) => `<optgroup label="${title}">` +
    D.regions.filter((r) => r.country === country && present.has(r.code))
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((r) => `<option value="${r.code}">${esc(r.name)}</option>`).join("") + "</optgroup>";
  $("#f-region").innerHTML = regOpts("CA", "Canada") + regOpts("US", "United States");
  $("#f-year").innerHTML = [...years].reverse().map((y) => `<option value="${y}">${y}</option>`).join("");
  $("#f-year").value = state.year;

  if (D.meta.synthetic) {
    const b = $("#banner"); b.hidden = false;
    b.innerHTML = "<strong>Demo data.</strong> These numbers are synthetic and only show how the dashboard works. " +
      "Run the data pipeline (see README) to load real figures from BEA and Statistics Canada.";
  }
  const latest = {};
  for (const r of D.rows) { const c = r[0].slice(0, 2); latest[c] = Math.max(latest[c] || 0, r[2]); }
  $("#notes").innerHTML =
    `<div>Sources: ${D.meta.sources.map(esc).join("; ")}. Generated ${esc(D.meta.generated.slice(0, 10))}. Latest year: ` +
    Object.entries(latest).map(([c, y]) => `${c} ${y}`).join(", ") + ".</div>" +
    "<div>Official spending data is annual and lags by 1 to 2 years, so this shows structural patterns, not this month's sales.</div>" +
    "<div>US figures are dollars per person (BEA); Canadian figures are dollars per household (Statistics Canada). " +
    "Regions are compared by share of budget and index, never by raw dollars across countries. Averages weight every region equally.</div>" +
    "<div>Categories are matched across agencies approximately (for example, US food includes restaurants and hotels; Canadian food does not split them), so small cross-country gaps can be definitional.</div>";

  $("#f-cat").onchange = (e) => { state.cat = e.target.value; render(); };
  $("#f-region").onchange = (e) => { state.region = e.target.value; render(); };
  $("#f-metric").onchange = (e) => { state.metric = e.target.value; render(); };
  $("#f-bench").onchange = (e) => { state.bench = e.target.value; render(); };
  $("#f-year").onchange = (e) => { state.year = +e.target.value; render(); };
  $("#f-real").onchange = (e) => { state.real = e.target.value === "real"; render(); };
  document.querySelectorAll("[data-trend]").forEach((b) => b.addEventListener("click", () => { state.trend = b.dataset.trend; render(); }));

  const maps = $("#maps");
  const tileOf = (e) => e.target.closest(".tile");
  maps.addEventListener("pointermove", (e) => { if (e.pointerType === "touch") return; const t = tileOf(e); if (t) tileTip(t.dataset.code, e.clientX, e.clientY); else hideTip(); });
  maps.addEventListener("pointerleave", hideTip);
  maps.addEventListener("focusin", (e) => { const t = tileOf(e); if (t) { const b = t.getBoundingClientRect(); tileTip(t.dataset.code, b.right, b.top); } });
  maps.addEventListener("focusout", hideTip);
  maps.addEventListener("click", (e) => { const t = tileOf(e); if (t) { state.region = t.dataset.code; render(); } });
  maps.addEventListener("keydown", (e) => { const t = tileOf(e); if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); state.region = t.dataset.code; render(); } });

  const pickCat = (e) => { const r = e.target.closest("[data-cat]"); if (r) { state.cat = r.dataset.cat; render(); } };
  for (const sel of ["#bars", "#momentum"]) {
    $(sel).addEventListener("click", pickCat);
    $(sel).addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickCat(e); } });
  }
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  matchMedia("(max-width: 640px)").addEventListener("change", render);
  // Redraw the trend chart when its width changes (rotating a phone, resizing a window).
  let lastW = 0;
  new ResizeObserver(() => {
    const w = $("#trend").clientWidth;
    if (Math.abs(w - lastW) >= 8) { lastW = w; renderTrend(); }
  }).observe($("#trend"));
  render();
}

fetch("data/spending.json")
  .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
  .then(init)
  .catch((e) => {
    $("#app").innerHTML = `<div class="card"><h2>Couldn't load the data</h2><p class="hint">${esc(e.message)}. ` +
      `Serve this folder over HTTP (python -m http.server -d web) rather than opening the file directly, ` +
      `and make sure web/data/spending.json exists (python -m pipeline.make_demo_data for demo data).</p></div>`;
  });
})();