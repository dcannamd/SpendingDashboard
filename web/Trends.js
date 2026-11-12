/* Search interest (Google Trends) for daily-living aids.
   Independent of app.js and detail.js. It listens for "dash:render" and reads
   data/trends.json. If that file is missing, the card stays hidden. */
(() => {
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const signed = (v, d = 0) => { if (v == null) return "–"; const r = +v.toFixed(d); return (r > 0 ? "+" : r < 0 ? "−" : "") + Math.abs(r).toFixed(d); };
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const COUNTRY = { US: "the US", CA: "Canada" };
const HEAD = { US: "US", CA: "Canada" };

const ui = { group: "all", sort: "relative", sel: null, justPicked: false };
let DATA = null, loading = false, last = null, wired = false, lastW = 0;

/* ---------- helpers ---------- */
function regionIndex(e, region) {
  const vals = e.region ? Object.values(e.region) : [];
  if (!vals.length || e.region[region] == null) return null;
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  return mean > 0 ? (e.region[region] / mean) * 100 : null;
}

function mini(m) {
  const v = (m || []).slice(-60);
  if (v.length < 3) return "";
  const lo = Math.min(...v), hi = Math.max(...v), W = 84, H = 24;
  const pts = v.map((y, i) => `${((i / (v.length - 1)) * (W - 2) + 1).toFixed(1)},${(H - 2 - ((y - lo) / (hi - lo || 1)) * (H - 4)).toFixed(1)}`).join(" ");
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${cssv("--s1")}" stroke-width="1.6"/></svg>`;
}

function chart(e, start, W) {
  const m = e.m || [];
  if (m.length < 3) return "";
  const H = 170, L = 38, R = 14, T = 10, B = 24;
  const hi = Math.max(10, Math.ceil(Math.max(...m) / 10) * 10);
  const x = (i) => L + (i / (m.length - 1)) * (W - L - R);
  const y = (v) => T + (1 - v / hi) * (H - T - B);
  const d = m.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1)).join("");
  const [sy, sm] = start.split("-").map(Number);
  const label = (i) => { const t = (sy * 12 + (sm - 1) + i); return `${Math.floor(t / 12)}`; };
  const ticks = [];
  for (let i = 0; i < m.length; i++) {
    const t = sy * 12 + (sm - 1) + i;
    if (t % 12 === 0 && i < m.length - 2) ticks.push(i);
  }
  const startRoom = !ticks.length || x(ticks[0]) - L > 44;
  const grid = [0, hi / 2, hi].map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${cssv("--grid")}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v)}</text>`).join("");
  const xl = ticks.map((i) => `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${label(i)}</text>`).join("");
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Search interest over five years">
    ${grid}<path d="${d}" fill="none" stroke="${cssv("--s1")}" stroke-width="2.2"/>
    <circle cx="${x(m.length - 1)}" cy="${y(m[m.length - 1])}" r="3.5" fill="${cssv("--s1")}"/>${xl}
    ${startRoom ? `<text x="${L}" y="${H - 6}" text-anchor="start">${sy}</text>` : ""}</svg>`;
}

const rising = (v) => (typeof v === "number" ? (v >= 5000 ? "Breakout" : `+${v}%`) : esc(v));

/* ---------- render ---------- */
function render(ctx) {
  const card = $("#gt-card");
  if (!card || !DATA || !ctx || !ctx.region) return;
  const reg = ctx.regions.find((r) => r.code === ctx.region);
  if (!reg) return;
  const geo = DATA.geo[reg.country];
  card.hidden = false;
  if (!geo) { $("#gt-body").innerHTML = `<p class="hint">No search data for ${esc(COUNTRY[reg.country])} yet.</p>`; return; }

  const rows = DATA.terms.map((t) => ({ t, e: geo.terms[t.id] })).filter((x) => x.e)
    .map((x) => ({ ...x, idx: regionIndex(x.e, ctx.region) }));
  const hasRegion = rows.some((x) => x.idx != null);

  $("#gt-h").textContent = `Search interest: daily-living aids (${HEAD[reg.country]})`;
  $("#gt-hint").textContent =
    `What people in ${COUNTRY[reg.country]} search for on Google, over the last 12 months. 100 is the most searched term on this list; ` +
    `the rest are relative to it. This is search interest, not sales, and it isn't a count of searches. ` +
    `Growth across nearly all terms is unusually high, which can reflect shifts in overall search behaviour as well as demand, so compare terms with each other ("vs typical") rather than reading the raw percentages as demand growth. ` +
    `Terms tagged "Rough data" are measured coarsely by Google in this comparison, so ignore their growth figures.`;

  const solid = rows.filter((x) => !x.e.low);
  const ys = solid.filter((x) => x.e.yoy != null).map((x) => x.e.yoy).sort((a, b) => a - b);
  const med = ys.length ? (ys.length % 2 ? ys[(ys.length - 1) / 2] : (ys[ys.length / 2 - 1] + ys[ys.length / 2]) / 2) : null;
  rows.forEach((x) => { x.rel = med != null && x.e.yoy != null ? x.e.yoy - med : null; });
  const topG = solid.filter((x) => x.rel != null).sort((a, b) => b.rel - a.rel).slice(0, 3);
  const topL = rows.filter((x) => x.e.level != null).sort((a, b) => b.e.level - a.e.level).slice(0, 3);
  const topR = solid.filter((x) => x.idx != null && x.idx >= 115).sort((a, b) => b.idx - a.idx).slice(0, 3);
  const parts = [];
  if (topL.length) parts.push(`Most searched: ${topL.map((x) => `<b>${esc(x.t.label)}</b>`).join(", ")}.`);
  if (med != null) parts.push(`Almost every search grew, so judge each against the typical term, which grew ${signed(med)}% over the past year.`);
  if (topG.length) parts.push(`Growing faster than typical: ${topG.map((x) => `<b>${esc(x.t.label)}</b> (${signed(x.rel)} points above)`).join(", ")}.`);
  if (topR.length) parts.push(`Where ${esc(reg.name)} searches more than the ${esc(COUNTRY[reg.country])} average: ${topR.map((x) => `<b>${esc(x.t.label)}</b> (index ${Math.round(x.idx)})`).join(", ")}.`);
  $("#gt-lead").innerHTML = parts.map((p) => `<p>${p}</p>`).join("");

  const gSel = $("#gt-group");
  gSel.innerHTML = `<option value="all">All groups</option>` + DATA.groups.filter((g) => rows.some((x) => x.t.group === g.id))
    .map((g) => `<option value="${esc(g.id)}">${esc(g.label)}</option>`).join("");
  if (![...gSel.options].some((o) => o.value === ui.group)) ui.group = "all";
  gSel.value = ui.group;
  $("#gt-sort").value = ui.sort;

  const shown = rows.filter((x) => ui.group === "all" || x.t.group === ui.group);
  const key = { relative: (x) => x.rel, growth: (x) => x.e.yoy, growth3: (x) => x.e.y3, level: (x) => x.e.level, region: (x) => x.idx }[ui.sort];
  shown.sort((p, q) => {
    if (ui.sort !== "level" && p.e.low !== q.e.low) return p.e.low ? 1 : -1;
    const a = key(p), b = key(q);
    if (a == null) return 1; if (b == null) return -1; return b - a;
  });
  const cls = (v) => (v == null || Math.abs(v) < 1 ? "" : v > 0 ? "pos" : "neg");
  const groupName = (id) => (DATA.groups.find((g) => g.id === id) || { label: id }).label;
  const body = shown.map(({ t, e, idx, rel }) => `<tr data-term="${esc(t.id)}" tabindex="0" class="${ui.sel === t.id ? "sel" : ""}">
      <td>${esc(t.label)}</td>
      <td class="hide-s">${esc(groupName(t.group))}</td>
      <td class="n"><span class="lvl"><i style="width:${Math.max(2, e.level || 0)}%"></i></span><span class="lvn">${e.level == null ? "–" : Math.round(e.level)}</span></td>
      <td class="n ${cls(e.yoy)}">${e.yoy == null ? "–" : signed(e.yoy) + "%"}</td>
      <td class="n ${cls(rel)}">${rel == null ? "–" : signed(rel) + " pts"}</td>
      <td class="n ${cls(e.y3)} hide-s">${e.y3 == null ? "–" : signed(e.y3) + "%"}</td>
      ${hasRegion ? `<td class="n hide-s">${idx == null ? "–" : Math.round(idx)}</td>` : ""}
      <td class="n hide-s">${mini(e.m)}</td>
      <td class="n">${e.low ? `<span class="badge small" title="Google's whole-number rounding is too coarse for this term in this comparison, so its growth figure is unreliable.">Rough data</span>` : ""}</td></tr>`).join("");
  $("#gt-body").innerHTML = `<table><thead><tr><th>Search term</th><th class="hide-s">Group</th><th class="n">Interest</th>
      <th class="n">1-yr change</th><th class="n">vs typical</th><th class="n hide-s">3-yr change</th>${hasRegion ? `<th class="n hide-s">In ${esc(reg.name)}</th>` : ""}
      <th class="n hide-s">5-yr trend</th><th class="n"></th></tr></thead><tbody>${body || `<tr><td colspan="9">Nothing in this group.</td></tr>`}</tbody></table>`;

  const focus = $("#gt-focus");
  const cur = ui.sel && rows.find((x) => x.t.id === ui.sel);
  if (!cur) { focus.innerHTML = ""; return; }
  const { t, e } = cur;
  const top = e.region ? Object.entries(e.region).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([code, v]) => {
    const r = ctx.regions.find((x) => x.code === code);
    return `<li${code === ctx.region ? ' class="me"' : ""}><span>${esc(r ? r.name : code)}</span><span>${v} of 100</span></li>`;
  }).join("") : "";
  const rel = (list, rise) => (list || []).map(([q, v]) => `<li><span>${esc(q)}</span><span>${rise ? rising(v) : ""}</span></li>`).join("");
  focus.innerHTML = `<div class="focus">
    <h3>${esc(t.label)}: searches for "${esc(t.term)}"</h3>
    <p class="hint">Monthly search interest over five years, ${esc(COUNTRY[reg.country])}. ${e.low ? "Rough data: treat the shape with caution." : ""}</p>
    <div class="chart gt-chart"></div>
    ${top ? `<h4>Where people search most</h4><p class="hint">100 is the state or province with the highest share of searches for this term.</p><ol class="toplist">${top}</ol>` : `<p class="hint">Regional detail wasn't collected (the quick run skips it).</p>`}
    ${(e.rising && e.rising.length) || (e.top && e.top.length) ? `<div class="two">
      ${e.top && e.top.length ? `<div><h4>People also search for</h4><ul class="toplist">${rel(e.top, false)}</ul></div>` : ""}
      ${e.rising && e.rising.length ? `<div><h4>Fastest-rising related searches</h4><ul class="toplist">${rel(e.rising, true)}</ul></div>` : ""}</div>
      <p class="hint">Look for words that describe a missing feature or style, such as "removable," "stylish," "for small bathrooms" or "no drilling." Those are hints at unmet needs, worth checking against product reviews.</p>` : ""}
  </div>`;
  const box = focus.querySelector(".gt-chart");
  box.innerHTML = chart(e, geo.start, Math.max(260, Math.floor(box.clientWidth)));
  if (ui.justPicked) { ui.justPicked = false; focus.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
}

/* ---------- wiring ---------- */
function wire() {
  if (wired) return; wired = true;
  const sortSel = $("#gt-sort");
  if (![...sortSel.options].some((o) => o.value === "relative")) sortSel.insertAdjacentHTML("afterbegin", '<option value="relative">Growing faster than typical</option>');
  $("#gt-group").addEventListener("change", (e) => { ui.group = e.target.value; render(last); });
  $("#gt-sort").addEventListener("change", (e) => { ui.sort = e.target.value; render(last); });
  const pick = (e) => { const r = e.target.closest("[data-term]"); if (r) { ui.sel = ui.sel === r.dataset.term ? null : r.dataset.term; ui.justPicked = !!ui.sel; render(last); } };
  $("#gt-body").addEventListener("click", pick);
  $("#gt-body").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(e); } });
}

function handle(ctx) {
  last = ctx;
  if (DATA) { render(ctx); return; }
  if (loading) return;
  loading = true;
  fetch("data/trends.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((d) => { DATA = d; wire(); render(last); })
    .catch(() => { /* no trends file: the card stays hidden */ });
}

window.addEventListener("dash:render", (e) => handle(e.detail));
if (window.__dashLast) handle(window.__dashLast);
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => last && render(last));
addEventListener("resize", () => { const b = document.querySelector(".gt-chart"); if (b && Math.abs(b.clientWidth - lastW) >= 8) { lastW = b.clientWidth; ui.justPicked = false; render(last); } });
})();