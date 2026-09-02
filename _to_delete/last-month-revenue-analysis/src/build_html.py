"""Build the self-contained interactive audit report."""
import os
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "out")
DIST = os.path.join(HERE, "..")


def measure_of(row):
    if row["source"] == "items":
        return "items+freight" if row["freight"] == "incl" else "items only"
    return "paid total" if row["voucher"] == "incl" else "paid ex-voucher"


def main():
    rev = pd.read_csv(f"{OUT}/revenue_by_definition.csv")
    months = pd.read_csv(f"{OUT}/months.csv")
    comp = set(months.loc[months["complete"], "ym"])
    rev = rev[rev["ym"].isin(comp)].copy()
    rev["measure"] = rev.apply(measure_of, axis=1)

    with open(f"{OUT}/summary.json") as fh:
        summary = json.load(fh)
    spread = pd.read_csv(f"{OUT}/spread_revenue.csv")
    flips = pd.read_csv(f"{OUT}/decision_flips.csv")
    cr = pd.read_csv(f"{OUT}/conditional_robustness.csv")

    anchors = ["purchase", "approved", "carrier", "delivered"]
    measures = ["items+freight", "items only", "paid total", "paid ex-voucher"]
    statuses = ["all", "ex_canceled", "ex_canceled_unavail", "delivered_only"]
    ym_list = sorted(comp)

    # cube[anchor][measure][status][ym] = revenue
    cube = {}
    for (a, m, s), g in rev.groupby(["anchor", "measure", "status"]):
        cube.setdefault(a, {}).setdefault(m, {})[s] = {
            r.ym: round(float(r.revenue), 2) for r in g.itertuples()}

    payload = {
        "anchors": anchors, "measures": measures, "statuses": statuses,
        "months": ym_list, "cube": cube,
        "focal": summary["focal_revenue"],
        "spread": [{"ym": r.ym, "pct": round(float(r.spread_pct), 2)}
                   for r in spread.itertuples()],
        "flipMonths": summary["flip_months"],
        "robustness": [
            {"dim": r.held_fixed, "level": r.level,
             "flipPct": round(float(r.flip_pct), 1),
             "spread": round(float(r.median_spread_pct), 1)}
            for r in cr.itertuples()],
        "stats": {
            "nDefs": summary["n_definitions"],
            "nMonths": summary["n_complete_months"],
            "medianSpread": round(summary["spread_pct_median_across_months"], 1),
            "nFlips": summary["n_flips"], "nPairs": summary["n_month_pairs"],
            "flipPct": round(summary["flip_pct"]),
            "levelShares": {k: round(100 * v, 1)
                            for k, v in summary["variance_shares_mean"].items()},
            "growthShares": {k: round(100 * v, 1) for k, v in
                             summary["growth_variance_shares_mean"].items()},
            "repeat": summary["repeat_rate"],
            "delivMin": round(summary["delivery_focal_min_days"], 1),
            "delivMax": round(summary["delivery_focal_max_days"], 1),
        },
    }

    html = TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
    path = os.path.join(DIST, "revenue_definition_audit.html")
    with open(path, "w") as fh:
        fh.write(html)
    print(f"wrote {path}  ({os.path.getsize(path)/1024:.0f} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What was revenue last month? — a definition audit</title>
<style>
  :root{
    color-scheme: light;
    --surface-0:#f6f5f2; --surface-1:#fcfcfb; --surface-2:#efeeea;
    --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#8a8985;
    --line:#e2e1dc;
    --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --neutral:#8a8985;
  }
  @media (prefers-color-scheme: dark){
    :root:where(:not([data-theme="light"])){
      color-scheme: dark;
      --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#242422;
      --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8f8e86;
      --line:#333330;
      --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --neutral:#8f8e86;
    }
  }
  :root[data-theme="dark"]{
    color-scheme: dark;
    --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#242422;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8f8e86;
    --line:#333330;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --neutral:#8f8e86;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--surface-0);color:var(--text-primary);
    font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1000px;margin:0 auto;padding:40px 24px 80px}
  header{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;
    margin-bottom:8px}
  h1{font-size:30px;line-height:1.2;margin:0 0 8px;letter-spacing:-.02em}
  h2{font-size:19px;margin:44px 0 6px;letter-spacing:-.01em}
  h3{font-size:14px;margin:0 0 14px;color:var(--text-secondary);font-weight:600;
    text-transform:uppercase;letter-spacing:.06em}
  p{margin:0 0 14px;color:var(--text-secondary);max-width:70ch}
  .lede{font-size:17px;color:var(--text-secondary);max-width:66ch}
  .card{background:var(--surface-1);border:1px solid var(--line);border-radius:14px;
    padding:22px 24px;margin:18px 0}
  .toggle{background:var(--surface-1);border:1px solid var(--line);border-radius:999px;
    padding:7px 14px;font-size:13px;color:var(--text-secondary);cursor:pointer;
    white-space:nowrap}
  .toggle:hover{border-color:var(--text-muted)}
  .hero{display:flex;flex-wrap:wrap;gap:14px;margin:22px 0}
  .tile{flex:1 1 190px;background:var(--surface-1);border:1px solid var(--line);
    border-radius:14px;padding:18px 20px}
  .tile .k{font-size:12px;color:var(--text-muted);text-transform:uppercase;
    letter-spacing:.06em;margin-bottom:8px}
  .tile .v{font-size:27px;font-weight:650;letter-spacing:-.02em;line-height:1.1}
  .tile .s{font-size:13px;color:var(--text-secondary);margin-top:6px}
  .controls{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:20px}
  .ctl{flex:1 1 210px;min-width:190px}
  .ctl label{display:block;font-size:12px;color:var(--text-muted);margin-bottom:7px;
    text-transform:uppercase;letter-spacing:.06em}
  .seg{display:flex;flex-wrap:wrap;gap:5px}
  .seg button{flex:1 1 auto;background:var(--surface-2);border:1px solid transparent;
    color:var(--text-secondary);border-radius:8px;padding:7px 9px;font-size:12.5px;
    cursor:pointer;font-family:inherit}
  .seg button:hover{border-color:var(--line)}
  .seg button[aria-pressed="true"]{background:var(--s1);color:#fff;font-weight:600}
  select{background:var(--surface-2);border:1px solid var(--line);color:var(--text-primary);
    border-radius:8px;padding:8px 10px;font-size:13px;font-family:inherit;width:100%}
  .readout{display:flex;flex-wrap:wrap;align-items:baseline;gap:14px;
    padding:16px 0 4px;border-top:1px solid var(--line);margin-top:6px}
  .readout .big{font-size:34px;font-weight:680;letter-spacing:-.025em}
  .readout .note{font-size:13.5px;color:var(--text-secondary)}
  svg{display:block;width:100%;height:auto;overflow:visible}
  .tick{font-size:11px;fill:var(--text-muted)}
  .glabel{font-size:12px;fill:var(--text-secondary)}
  .grid{stroke:var(--line);stroke-width:1}
  table{border-collapse:collapse;width:100%;font-size:13px;margin-top:6px}
  th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
  th{color:var(--text-muted);font-weight:600;font-size:11.5px;text-transform:uppercase;
    letter-spacing:.05em}
  td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
  .hide{display:none}
  .tip{position:fixed;pointer-events:none;background:var(--surface-1);
    border:1px solid var(--line);border-radius:9px;padding:9px 11px;font-size:12.5px;
    box-shadow:0 6px 22px rgba(0,0,0,.14);opacity:0;transition:opacity .1s;z-index:9}
  .tip b{color:var(--text-primary)}
  .legend{display:flex;flex-wrap:wrap;gap:16px;margin:10px 0 2px;font-size:12.5px;
    color:var(--text-secondary)}
  .legend i{display:inline-block;width:11px;height:11px;border-radius:3px;
    margin-right:6px;vertical-align:-1px}
  footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
    font-size:13px;color:var(--text-muted)}
  a{color:var(--s1)}
  .cap{font-size:13px;color:var(--text-muted);margin-top:10px}
</style></head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>What was revenue last month?</h1>
    <p class="lede">The same 99,441 orders, 64 defensible definitions, and a
      R$508,784 gap between the smallest and largest defensible answer for
      August 2018.</p>
  </div>
  <button class="toggle" id="theme">Dark</button>
</header>

<div class="hero" id="hero"></div>

<h2>Move the definition, watch the number</h2>
<p>Every control below is a choice a competent analyst could defend. None of them
   is a mistake. Pick a combination and see what the business reported that month.</p>

<div class="card">
  <div class="controls">
    <div class="ctl"><label>Period anchor</label><div class="seg" id="segAnchor"></div></div>
    <div class="ctl"><label>Revenue measure</label><div class="seg" id="segMeasure"></div></div>
    <div class="ctl"><label>Status scope</label><div class="seg" id="segStatus"></div></div>
    <div class="ctl" style="flex:0 1 150px"><label>Month</label>
      <select id="selMonth"></select></div>
  </div>
  <div class="readout">
    <div class="big" id="roValue">—</div>
    <div class="note" id="roNote"></div>
  </div>
  <svg id="strip" viewBox="0 0 900 150" role="img"
       aria-label="All 64 definitions for the selected month"></svg>
  <div class="legend" id="stripLegend"></div>
  <p class="cap">Each dot is one definition. The ring marks your current selection.</p>
</div>

<h2>The anchor moves revenue between months</h2>
<p>Identical orders, identical money. The only thing changing is which timestamp
   decides the month an order lands in. Black Friday orders are purchased in
   November and delivered in December — so a purchase-anchored November spikes
   while a delivery-anchored November is flat.</p>
<div class="card">
  <svg id="lines" viewBox="0 0 900 380" role="img"
       aria-label="Monthly revenue under each period anchor"></svg>
  <div class="legend" id="lineLegend"></div>
  <button class="toggle" id="tblToggle" style="margin-top:14px">Show table</button>
  <div id="tblWrap" class="hide" style="margin-top:14px;max-height:340px;overflow:auto"></div>
</div>

<h2>Different choices break different numbers</h2>
<p>The measure choice (freight in or out, items or payments) applies a roughly
   constant multiplier every month, so it moves the level a lot and growth barely
   at all. The anchor <em>relocates</em> revenue between months — which is exactly
   what corrupts a month-over-month comparison.</p>
<div class="card"><svg id="attr" viewBox="0 0 900 230" role="img"
     aria-label="Share of variance by choice, levels versus growth"></svg>
  <div class="legend" id="attrLegend"></div></div>

<h2>Spread by month, and where the growth call breaks</h2>
<div class="card"><svg id="bars" viewBox="0 0 900 280" role="img"
     aria-label="Definition spread by month"></svg>
  <div class="legend" id="barLegend"></div>
  <p class="cap" id="barCap"></p></div>

<h2>If you standardise exactly one thing</h2>
<div class="card"><div id="robust"></div>
  <p class="cap">Fixing the period anchor removes nearly all disagreement about
    direction. Fixing the measure removes almost none of it. Fixing the
    cancellation policy — the argument teams have most often — does nothing.</p>
</div>

<h2>Two adjacent traps</h2>
<div class="card" id="traps"></div>

<footer>
  Data: <a href="https://github.com/olist/work-at-olist-data">Olist Brazilian
  E-Commerce Public Dataset</a> (Olist's own GitHub organisation), 99,441 orders,
  Jan 2017 – Aug 2018. Boundary months excluded as partial exports.
  Full method and limitations in <code>REPORT.md</code>; recommended definitions in
  <code>METRIC_SPEC.md</code>.
</footer>
</div>
<div class="tip" id="tip"></div>

<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const ANCHOR_LBL = {purchase:"Purchase", approved:"Approved", carrier:"Shipped",
                    delivered:"Delivered"};
const STATUS_LBL = {all:"All", ex_canceled:"Ex-cancelled",
                    ex_canceled_unavail:"Ex-cancelled + unavailable",
                    delivered_only:"Delivered only"};
const brl = v => "R$" + (v>=1e6 ? (v/1e6).toFixed(2)+"M" : Math.round(v/1e3)+"k");
const brlFull = v => "R$" + v.toLocaleString("en-US",{maximumFractionDigits:0});
const anchorColor = a => css("--s"+(D.anchors.indexOf(a)+1));

let sel = {anchor:"purchase", measure:"items+freight", status:"all",
           ym:D.focal.month};

/* ---------- theme ---------- */
$("#theme").onclick = () => {
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
  $("#theme").textContent = dark ? "Dark" : "Light";
  drawAll();
};

/* ---------- tooltip ---------- */
const tip = $("#tip");
function showTip(e, html){
  tip.innerHTML = html; tip.style.opacity = 1;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY - r.height - 10;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y < 8) y = e.clientY + 16;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
const hideTip = () => tip.style.opacity = 0;

/* ---------- hero ---------- */
function hero(){
  const f = D.focal, s = D.stats;
  $("#hero").innerHTML = [
    ["Lowest defensible answer", brlFull(f.min), f.lowest_def.replace(/\|/g," · ")],
    ["Highest defensible answer", brlFull(f.max), f.highest_def.replace(/\|/g," · ")],
    ["Spread, August 2018", f.spread_pct.toFixed(0)+"%", f.ratio.toFixed(2)+"x from low to high"],
    ["Growth calls contradicted", s.nFlips+" of "+s.nPairs,
     "months where definitions disagree on the sign"]
  ].map(([k,v,sub]) =>
    `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div>
     <div class="s">${sub}</div></div>`).join("");
}

/* ---------- controls ---------- */
function segs(){
  const mk = (id, vals, key, lbl) => {
    $(id).innerHTML = vals.map(v =>
      `<button role="button" data-v="${v}" aria-pressed="${sel[key]===v}">${lbl(v)}</button>`
    ).join("");
    $(id).onclick = e => {
      const b = e.target.closest("button"); if(!b) return;
      sel[key] = b.dataset.v; segs(); update();
    };
  };
  mk("#segAnchor", D.anchors, "anchor", v => ANCHOR_LBL[v]);
  mk("#segMeasure", D.measures, "measure", v => v);
  mk("#segStatus", D.statuses, "status", v => STATUS_LBL[v]);
}
function monthSel(){
  $("#selMonth").innerHTML = D.months.map(m =>
    `<option ${m===sel.ym?"selected":""}>${m}</option>`).join("");
  $("#selMonth").onchange = e => { sel.ym = e.target.value; update(); };
}

const valuesFor = ym => {
  const out = [];
  for (const a of D.anchors) for (const m of D.measures) for (const s of D.statuses){
    const v = D.cube[a]?.[m]?.[s]?.[ym];
    if (v != null) out.push({a, m, s, v});
  }
  return out.sort((x,y) => x.v - y.v);
};

/* ---------- strip ---------- */
function strip(){
  const svg = $("#strip"); svg.innerHTML = "";
  const W=900, H=150, L=18, R=18, T=30, B=34;
  const vals = valuesFor(sel.ym);
  const lo = Math.min(...vals.map(d=>d.v)), hi = Math.max(...vals.map(d=>d.v));
  const pad = (hi-lo)*0.06 || 1;
  const x = v => L + (v-(lo-pad))/((hi+pad)-(lo-pad))*(W-L-R);
  const add = (t,at) => { const e=document.createElementNS(NS,t);
    for(const k in at) e.setAttribute(k, at[k]); svg.appendChild(e); return e; };

  for (let i=0;i<=4;i++){
    const v = lo-pad + i*((hi+pad)-(lo-pad))/4;
    add("line",{x1:x(v),x2:x(v),y1:T-8,y2:H-B,class:"grid"});
    const t = add("text",{x:x(v),y:H-B+18,class:"tick","text-anchor":"middle"});
    t.textContent = brl(v);
  }
  const rows = 4, gap = (H-B-T)/rows;
  vals.forEach((d,i) => {
    const cy = T + (i % rows) * gap + gap/2;
    const on = d.a===sel.anchor && d.m===sel.measure && d.s===sel.status;
    const c = add("circle",{cx:x(d.v), cy, r: on?7.5:4.6, fill:anchorColor(d.a),
      stroke: on?css("--text-primary"):css("--surface-1"),
      "stroke-width": on?2.4:1.3, style:"cursor:pointer"});
    c.addEventListener("mousemove", e => showTip(e,
      `<b>${brlFull(d.v)}</b><br>${ANCHOR_LBL[d.a]} anchor · ${d.m}<br>${STATUS_LBL[d.s]}`));
    c.addEventListener("mouseleave", hideTip);
    c.addEventListener("click", () => { sel.anchor=d.a; sel.measure=d.m; sel.status=d.s;
      segs(); update(); });
  });
  $("#stripLegend").innerHTML = D.anchors.map(a =>
    `<span><i style="background:${anchorColor(a)}"></i>${ANCHOR_LBL[a]}</span>`).join("");
}

/* ---------- readout ---------- */
function readout(){
  const vals = valuesFor(sel.ym);
  const v = D.cube[sel.anchor]?.[sel.measure]?.[sel.status]?.[sel.ym];
  if (v == null){ $("#roValue").textContent = "n/a"; $("#roNote").textContent=""; return; }
  const rank = vals.findIndex(d => d.v === v) + 1;
  const lo = vals[0].v, hi = vals[vals.length-1].v;
  const pct = ((v/lo)-1)*100;
  $("#roValue").textContent = brlFull(v);
  $("#roNote").innerHTML =
    `rank <b>${rank}</b> of ${vals.length} · ${pct.toFixed(0)}% above the lowest
     defensible answer for ${sel.ym} · range ${brl(lo)}–${brl(hi)}`;
}

/* ---------- lines ---------- */
function lines(){
  const svg = $("#lines"); svg.innerHTML = "";
  const W=900,H=380,L=62,R=96,T=16,B=42;
  const ms = D.months;
  const series = D.anchors.map(a => ({a, vals: ms.map(m =>
    D.cube[a]?.[sel.measure]?.[sel.status]?.[m] ?? null)}));
  const flat = series.flatMap(s => s.vals).filter(v => v!=null);
  const rawHi = Math.max(...flat)*1.06;
  const step = Math.pow(10, Math.floor(Math.log10(rawHi/4)));
  const nice = [1,1.5,2,2.5,3,4,5,7.5,10].map(k=>k*step).find(k=>k*4>=rawHi) || rawHi/4;
  const hi = nice*4;
  const x = i => L + i*(W-L-R)/(ms.length-1);
  const y = v => H-B - v/hi*(H-B-T);
  const add = (t,at,txt) => { const e=document.createElementNS(NS,t);
    for(const k in at) e.setAttribute(k, at[k]);
    if(txt!=null) e.textContent=txt; svg.appendChild(e); return e; };

  for(let i=0;i<=4;i++){
    const v = hi*i/4;
    add("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),class:"grid"});
    add("text",{x:L-10,y:y(v)+4,class:"tick","text-anchor":"end"}, brl(v));
  }
  ms.forEach((m,i) => { if(i%3===0)
    add("text",{x:x(i),y:H-B+20,class:"tick","text-anchor":"middle"}, m); });

  const nov = ms.indexOf("2017-11");
  if(nov>=0){
    add("line",{x1:x(nov),x2:x(nov),y1:T,y2:H-B,stroke:css("--text-muted"),
      "stroke-width":1,"stroke-dasharray":"3 3"});
    add("text",{x:x(nov)+6,y:T+12,class:"glabel"},"Black Friday");
  }
  const ends = [];
  series.forEach(s => {
    const d = s.vals.map((v,i) => v==null?null:`${i===0?"M":"L"}${x(i)},${y(v)}`)
      .filter(Boolean).join(" ");
    add("path",{d, fill:"none", stroke:anchorColor(s.a), "stroke-width":2,
      "stroke-linejoin":"round","stroke-linecap":"round"});
    ends.push({a:s.a, v:s.vals[s.vals.length-1]});
  });
  // place labels top-down, nudging each at least 15px below the previous, then
  // leader-line back to the true endpoint so the label still reads as anchored
  ends.sort((p,q)=>q.v-p.v);
  let prev = -Infinity;
  ends.forEach(e => {
    let ly = y(e.v);
    if (ly < prev + 15) ly = prev + 15;
    prev = ly;
    add("text",{x:W-R+13,y:ly+4,class:"glabel",fill:anchorColor(e.a),
      "font-weight":"600"}, ANCHOR_LBL[e.a]);
    if (Math.abs(ly - y(e.v)) > 0.5)
      add("path",{d:`M${W-R},${y(e.v)} L${W-R+9},${ly}`,fill:"none",
        stroke:anchorColor(e.a),"stroke-width":1,opacity:.75});
  });

  const hit = add("rect",{x:L,y:T,width:W-L-R,height:H-B-T,fill:"transparent",
    style:"cursor:crosshair"});
  const cross = add("line",{x1:0,x2:0,y1:T,y2:H-B,stroke:css("--text-muted"),
    "stroke-width":1,opacity:0});
  hit.addEventListener("mousemove", e => {
    const bb = svg.getBoundingClientRect();
    const px = (e.clientX-bb.left)/bb.width*W;
    const i = Math.max(0, Math.min(ms.length-1, Math.round((px-L)/((W-L-R)/(ms.length-1)))));
    cross.setAttribute("x1",x(i)); cross.setAttribute("x2",x(i));
    cross.setAttribute("opacity",1);
    const rows = series.map(s => `<span style="color:${anchorColor(s.a)}">&#9632;</span>
      ${ANCHOR_LBL[s.a]} <b>${s.vals[i]==null?"—":brlFull(s.vals[i])}</b>`).join("<br>");
    showTip(e, `<b>${ms[i]}</b><br>${rows}`);
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity",0); hideTip(); });

  $("#lineLegend").innerHTML = D.anchors.map(a =>
    `<span><i style="background:${anchorColor(a)}"></i>${ANCHOR_LBL[a]}</span>`).join("")
    + `<span style="color:var(--text-muted)">measure: ${sel.measure} · scope: ${STATUS_LBL[sel.status]}</span>`;

  $("#tblWrap").innerHTML = "<table><thead><tr><th>Month</th>" +
    D.anchors.map(a=>`<th class="num">${ANCHOR_LBL[a]}</th>`).join("") +
    "</tr></thead><tbody>" + ms.map((m,i) => "<tr><td>"+m+"</td>" +
      series.map(s=>`<td class="num">${s.vals[i]==null?"—":brlFull(s.vals[i])}</td>`).join("") +
      "</tr>").join("") + "</tbody></table>";
}
$("#tblToggle").onclick = () => {
  const w = $("#tblWrap"); const h = w.classList.toggle("hide");
  $("#tblToggle").textContent = h ? "Show table" : "Hide table";
};

/* ---------- attribution ---------- */
function attr(){
  const svg=$("#attr"); svg.innerHTML="";
  const W=900,H=230,L=150,R=60,T=14,B=34;
  const rows=[["anchor","Period anchor"],["measure","Revenue measure"],
              ["status","Status scope"]];
  const x=v=>L+v/100*(W-L-R);
  const add=(t,at,txt)=>{const e=document.createElementNS(NS,t);
    for(const k in at)e.setAttribute(k,at[k]); if(txt!=null)e.textContent=txt;
    svg.appendChild(e); return e;};
  for(let v=0;v<=100;v+=25){
    add("line",{x1:x(v),x2:x(v),y1:T,y2:H-B,class:"grid"});
    add("text",{x:x(v),y:H-B+18,class:"tick","text-anchor":"middle"},v+"%");
  }
  const gap=(H-B-T)/rows.length;
  rows.forEach(([k,lbl],i)=>{
    const cy=T+i*gap+gap/2;
    add("text",{x:L-12,y:cy+4,class:"glabel","text-anchor":"end"},lbl);
    [[D.stats.levelShares[k],css("--s1"),"Level",-1],
     [D.stats.growthShares[k],css("--s2"),"Growth",1]].forEach(([v,c,,dir])=>{
      const h=15, yy=cy+dir*(h/2+1)-h/2;
      add("rect",{x:L,y:yy,width:Math.max(2,x(v)-L),height:h,fill:c,rx:3});
      add("text",{x:x(v)+7,y:yy+h-3,class:"tick"},v.toFixed(0)+"%");
    });
  });
  $("#attrLegend").innerHTML =
    `<span><i style="background:${css("--s1")}"></i>Share of variance in the level</span>
     <span><i style="background:${css("--s2")}"></i>Share of variance in month-over-month growth</span>`;
}

/* ---------- bars ---------- */
function bars(){
  const svg=$("#bars"); svg.innerHTML="";
  const W=900,H=280,L=52,R=16,T=16,B=58;
  const d=D.spread, hi=Math.max(...d.map(r=>r.pct))*1.1;
  const bw=(W-L-R)/d.length;
  const y=v=>H-B-v/hi*(H-B-T);
  const add=(t,at,txt)=>{const e=document.createElementNS(NS,t);
    for(const k in at)e.setAttribute(k,at[k]); if(txt!=null)e.textContent=txt;
    svg.appendChild(e); return e;};
  for(let i=0;i<=4;i++){const v=hi*i/4;
    add("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),class:"grid"});
    add("text",{x:L-10,y:y(v)+4,class:"tick","text-anchor":"end"},v.toFixed(0)+"%");}
  const m = D.stats.medianSpread;
  d.forEach((r,i)=>{
    const first = i===0;
    const c = first ? css("--neutral")
      : (D.flipMonths.includes(r.ym) ? css("--s2") : css("--s1"));
    const b=add("rect",{x:L+i*bw+bw*0.16,y:y(r.pct),width:bw*0.68,
      height:(H-B)-y(r.pct),fill:c,rx:3,style:"cursor:pointer"});
    b.addEventListener("mousemove",e=>showTip(e,
      `<b>${r.ym}</b><br>spread ${r.pct.toFixed(1)}% of mean<br>` +
      (first ? "no prior month to compare"
             : (D.flipMonths.includes(r.ym) ? "growth call <b>contradicted</b>"
                                            : "growth call agreed"))));
    b.addEventListener("mouseleave",hideTip);
    if(i%2===0) add("text",{x:L+i*bw+bw/2,y:H-B+20,class:"tick",
      "text-anchor":"end",transform:`rotate(-45 ${L+i*bw+bw/2} ${H-B+20})`}, r.ym);
  });
  add("line",{x1:L,x2:W-R,y1:y(m),y2:y(m),stroke:css("--text-muted"),
    "stroke-width":1.4,"stroke-dasharray":"5 4"});
  add("text",{x:L+4,y:y(m)-7,class:"tick"},
    "median "+m.toFixed(1)+"%");
  $("#barLegend").innerHTML =
    `<span><i style="background:${css("--s2")}"></i>Growth call contradicted</span>
     <span><i style="background:${css("--s1")}"></i>Growth call agreed</span>
     <span><i style="background:${css("--neutral")}"></i>No prior month</span>`;
  $("#barCap").textContent =
    `January 2017 is the extreme at 109%: in a fast-ramping month, delivery lag `+
    `makes the anchor choice dominate everything else.`;
}

/* ---------- robustness ---------- */
function robust(){
  const g = {};
  D.robustness.forEach(r => {
    if(r.dim === "(nothing)") { g["Nothing standardised"] = r; return; }
    (g[r.dim] = g[r.dim] || []).push(r);
  });
  const rows = [["Nothing standardised", g["Nothing standardised"].flipPct,
                 g["Nothing standardised"].spread]];
  [["anchor","Standardise the period anchor"],
   ["measure","Standardise the revenue measure"],
   ["status","Standardise the status scope"]].forEach(([k,lbl])=>{
    const a=g[k]; rows.push([lbl,
      a.reduce((s,r)=>s+r.flipPct,0)/a.length,
      a.reduce((s,r)=>s+r.spread,0)/a.length]);
  });
  $("#robust").innerHTML = "<table><thead><tr><th>Policy</th>" +
    `<th class="num">Contradicted month-pairs</th><th class="num">Median spread</th>` +
    "</tr></thead><tbody>" + rows.map(([l,f,s],i)=>
      `<tr><td${i===1?' style="font-weight:650"':''}>${l}</td>
       <td class="num"${i===1?' style="font-weight:650;color:'+css("--s1")+'"':''}>${f.toFixed(0)}%</td>
       <td class="num">${s.toFixed(0)}%</td></tr>`).join("") + "</tbody></table>";
}

/* ---------- traps ---------- */
function traps(){
  const r = D.stats.repeat;
  const byId = Object.fromEntries(r.map(x=>[x.def_id,x]));
  $("#traps").innerHTML = `
    <h3>Repeat-purchase rate is degenerate by accident</h3>
    <p>Olist issues a new <code>customer_id</code> per order and keeps identity in
       <code>customer_unique_id</code>. The natural-looking query returns a number
       that is structurally always zero — and zero looks like a finding for a young
       marketplace, so it survives review.</p>
    <table><thead><tr><th>Identity key</th><th class="num">Repeat rate</th>
      <th class="num">Repeat customers</th></tr></thead><tbody>
      <tr><td><code>customer_id</code></td>
        <td class="num" style="color:${css("--s2")};font-weight:650">
        ${byId["customer_id|all"].repeat_rate_pct.toFixed(2)}%</td>
        <td class="num">0 of ${byId["customer_id|all"].n_customers.toLocaleString()}</td></tr>
      <tr><td><code>customer_unique_id</code></td>
        <td class="num" style="font-weight:650">
        ${byId["customer_unique_id|all"].repeat_rate_pct.toFixed(2)}%</td>
        <td class="num">${byId["customer_unique_id|all"].n_repeat.toLocaleString()}
        of ${byId["customer_unique_id|all"].n_customers.toLocaleString()}</td></tr>
    </tbody></table>
    <h3 style="margin-top:26px">Delivery time spans 2.1x</h3>
    <p>For August 2018, mean delivery time is between
       <b>${D.stats.delivMin} and ${D.stats.delivMax} days</b> depending on whether the
       clock starts at carrier handoff or purchase, and whether days are counted
       business or calendar. Neither is wrong; they answer different questions under
       one label.</p>`;
}

function update(){ readout(); strip(); lines(); }
function drawAll(){ hero(); segs(); monthSel(); readout(); strip(); lines();
  attr(); bars(); robust(); traps(); }
drawAll();
addEventListener("resize", () => { strip(); lines(); attr(); bars(); });
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
