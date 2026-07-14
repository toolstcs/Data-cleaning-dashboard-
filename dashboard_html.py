"""
Builds the dashboard as one self-contained HTML document, styled to match the
old Lead Database Dashboard: Inter, #f8f9fa page, white cards with a gradient
top rail, pill brand toggle, and horizontal bar rows.

Two reasons it is an iframe (components.html) rather than st.markdown:

1. Isolation. Streamlit's own theme leaks into injected markdown. If
   .streamlit/config.toml still says base = "dark", Streamlit paints text light,
   and any element of ours without an explicit colour renders white on white.
   That is exactly what made TOTAL RECORDS and UNIQUE CONTACTS invisible. An
   iframe has its own document and cannot be reached by Streamlit's CSS.

2. The brand toggle switches instantly in JS instead of triggering a Streamlit
   rerun and a fresh round of API calls, which is how the old dashboard felt.

The only thing that changes from the old app is what the bars measure. It was
leads per technology. It is now BLANKS per tracked field.
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from assets_loader import logo_src
from config import AMBER_AT, GREEN_AT, NUMBER_LOCALE


def build_payload(
    df: pd.DataFrame,
    rollup: pd.DataFrame,
    brands: list[dict],
    summary: dict | None,
    fetched_at: float,
) -> dict:
    """Everything the page needs, as plain JSON."""
    names = {b["key"]: b["name"] for b in brands}
    out_brands: dict[str, dict] = {}

    for brand in brands:
        key = brand["key"]
        row = rollup[rollup["brand_key"] == key]
        sub = df[df["brand_key"] == key]
        if row.empty:
            continue
        r = row.iloc[0]

        rows = [
            {
                "label": rec["field"],
                "prop": rec["property"],
                "total": int(rec["total"]),
                "blanks": int(rec["blanks"]),
                "filled": int(rec["filled"]),
                "pct": float(rec["completion"]),
            }
            for _, rec in sub.iterrows()
        ]

        overlap = {}
        if summary:
            for other in brands:
                if other["key"] == key:
                    continue
                n = int(summary["intersections"].get(frozenset([key, other["key"]]), 0))
                if n:
                    overlap[other["short"]] = n

        out_brands[key] = {
            "name": brand["name"],
            "short": brand["short"],
            "logo": logo_src(key, brand.get("logo")) or "",
            "marker": str(r["marker"] or ""),
            "accent": brand["accent"],
            "accent2": brand["accent2"],
            "records": int(r["records"]),
            "rows": rows,
            "totals": {
                "cells": int(r["cells"]),
                "blanks": int(r["blanks"]),
                "filled": int(r["filled"]),
                "pct": float(r["completion"]),
            },
            "overlap": overlap,
        }

    overall: dict = {}
    if summary:
        regions = []
        order = [b["key"] for b in brands]
        for keys, n in sorted(summary["regions"].items(), key=lambda kv: (len(kv[0]), -kv[1])):
            if n <= 0:
                continue
            parts = [b["short"] for b in brands if b["key"] in keys]
            label = " + ".join(parts) + (" only" if len(keys) == 1 else "")
            regions.append({"label": label, "n": int(n), "size": len(keys)})
        overall = {
            "unique": summary["unique"],
            "summed": summary["summed"],
            "in_multiple": summary["in_multiple"],
            "duplicated": summary["duplicated"],
            "regions": regions,
        }
        del order

    totals = {
        "blanks": int(rollup["blanks"].sum()) if not rollup.empty else 0,
        "filled": int(rollup["filled"].sum()) if not rollup.empty else 0,
        "cells": int(rollup["cells"].sum()) if not rollup.empty else 0,
    }
    totals["pct"] = (
        round(totals["filled"] / totals["cells"] * 100, 1) if totals["cells"] else 0.0
    )

    return {
        "order": [b["key"] for b in brands if b["key"] in out_brands],
        "brands": out_brands,
        "overall": overall,
        "totals": totals,
        "green": GREEN_AT,
        "amber": AMBER_AT,
        "locale": NUMBER_LOCALE,
        "updated": datetime.fromtimestamp(fetched_at).strftime("%d %b %Y, %H:%M"),
        "names": names,
    }


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#f8f9fa;--bg-card:#fff;--bg-el:#f1f3f5;--bdr:#e0e0e0;--bdr-l:#eee;
--txt:#1a1a1a;--txt-s:#666;--txt-m:#999;--accent:#4338ED;--accent2:#F97316;
--glow:rgba(67,56,237,0.15);--grad:linear-gradient(135deg,#4338ED,#6366F1);
--grad-bar:linear-gradient(90deg,#4338ED,#818CF8);
--good:#10B981;--warn:#F59E0B;--bad:#EF4444}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--txt);line-height:1.5}
.db{max-width:1180px;margin:0 auto;padding:28px 24px 48px}

.hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:26px;flex-wrap:wrap;gap:16px}
.hdr h1{font-size:24px;font-weight:900;color:var(--txt)}
.hdr h1 .hl{color:var(--accent)}
.hdr .sub{font-size:12px;color:var(--txt-s);margin-top:3px}
.hdr .brandmark{height:30px;max-width:150px;width:auto;object-fit:contain;display:block}
.tg{display:inline-flex;background:var(--bg-card);border-radius:12px;padding:4px;border:1px solid var(--bdr);flex-wrap:wrap}
.tb{padding:9px 20px;border:none;background:transparent;font-family:inherit;font-size:13px;font-weight:600;color:var(--txt-s);border-radius:9px;cursor:pointer;transition:all .25s;white-space:nowrap}
.tb:hover{color:var(--txt);background:var(--bg-el)}
.tb.on{background:var(--accent);color:#fff;box-shadow:0 4px 16px var(--glow)}

.sr{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:20px}
.sc{background:var(--bg-card);border-radius:16px;padding:22px 24px;border:1px solid var(--bdr);position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad)}
.sc .lb{font-size:10px;font-weight:700;color:var(--txt-s);text-transform:uppercase;letter-spacing:.7px;margin-bottom:8px}
.sc .vl{font-size:29px;font-weight:900;color:var(--txt);font-variant-numeric:tabular-nums}
.sc .vl.bad{color:var(--bad)} .sc .vl.good{color:var(--good)} .sc .vl.warn{color:var(--warn)}
.sc .sb{font-size:11px;color:var(--txt-m);margin-top:3px}
.sc .ic{position:absolute;top:18px;right:20px;width:36px;height:36px;border-radius:10px;background:rgba(99,102,241,.1);display:flex;align-items:center;justify-content:center;font-size:15px}

.olt{display:inline-block;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:700;background:rgba(249,115,22,.12);color:var(--accent2);border:1px solid rgba(249,115,22,.3);margin-right:6px}
.mkr{display:inline-block;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:600;background:var(--bg-el);color:var(--txt-s);border:1px solid var(--bdr);margin-right:6px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.pills{margin-bottom:24px;display:flex;flex-wrap:wrap;gap:4px;align-items:center}

.pn{background:var(--bg-card);border-radius:18px;padding:26px 28px;border:1px solid var(--bdr);margin-bottom:24px}
.pt{font-size:16px;font-weight:800;color:var(--txt)}
.ph{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:20px}
.mt{display:inline-flex;background:var(--bg-el);border-radius:8px;padding:2px;border:1px solid var(--bdr)}
.mt button{padding:5px 12px;border:none;background:transparent;font-family:inherit;font-size:10px;font-weight:700;color:var(--txt-m);border-radius:6px;cursor:pointer;transition:all .2s}
.mt button.on{background:var(--accent2);color:#fff}

.bc{display:flex;flex-direction:column;gap:9px}
.br{display:grid;grid-template-columns:170px 1fr 82px 82px 56px;align-items:center;gap:14px;padding:5px 0;border-radius:8px;transition:background .15s}
.br.wide{grid-template-columns:260px 1fr 92px 0 0}
.br:hover{background:rgba(0,0,0,.02)}
.bl{font-size:13px;font-weight:600;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bt{height:28px;background:var(--bg-el);border-radius:8px;overflow:hidden}
.bf{height:100%;border-radius:8px;transition:width .7s cubic-bezier(.22,1,.36,1);min-width:5px;position:relative}
.bf::after{content:'';position:absolute;top:0;right:0;width:40px;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.18));border-radius:0 8px 8px 0}
.bv{font-size:13px;font-weight:800;color:var(--txt);text-align:right;font-variant-numeric:tabular-nums}
.bv.sec{color:var(--txt-s);font-weight:600}
.bv.pct{font-weight:800}
.bv.good{color:var(--good)} .bv.warn{color:var(--warn)} .bv.bad{color:var(--bad)}
.bch{font-size:10px;font-weight:700;color:var(--txt-m);text-transform:uppercase;letter-spacing:.5px;text-align:right}
.bch.l{text-align:left}
.tr{display:grid;grid-template-columns:170px 1fr 82px 82px 56px;align-items:center;gap:14px;margin-top:14px;padding-top:14px;border-top:2px solid var(--accent)}
.tr .bl{font-weight:900;color:var(--accent);font-size:13px}
.tr .bv{font-weight:900;color:var(--accent)}
.tr .bv.sec{color:var(--accent2)}

.ovbar{display:flex;height:16px;border-radius:8px;overflow:hidden;background:var(--bg-el);margin-bottom:18px}
.ovseg{height:100%}
.foot{text-align:center;padding:22px 0 0;font-size:11px;color:var(--txt-m)}
.nd{text-align:center;padding:42px;color:var(--txt-m);font-size:14px}

@media(max-width:768px){
.db{padding:16px 12px}
.hdr{flex-direction:column;align-items:flex-start}
.sr{grid-template-columns:1fr 1fr}
.br,.tr{grid-template-columns:96px 1fr 60px 60px 44px;gap:8px}
.bl{font-size:11px}.bv{font-size:11px}
.pn{padding:18px 14px}
}
"""

JS = """
const D = __DATA__;
const ALL = '__all__';
let active = D.order[0] || ALL;
let sort = 'config';

const fmt = n => (n === null || n === undefined) ? '0' : n.toLocaleString(D.locale);
const band = p => p >= D.green ? 'good' : (p >= D.amber ? 'warn' : 'bad');

function theme(a, a2) {
  const s = document.documentElement.style;
  s.setProperty('--accent', a);
  s.setProperty('--accent2', a2);
  s.setProperty('--glow', a + '26');
  s.setProperty('--grad', 'linear-gradient(135deg,' + a + ',' + a + 'aa)');
  s.setProperty('--grad-bar', 'linear-gradient(90deg,' + a + ',' + a + '99)');
}

function statCard(label, value, icon, cls, sub) {
  return '<div class="sc"><div class="lb">' + label + '</div>' +
         '<div class="vl ' + (cls || '') + '">' + value + '</div>' +
         (sub ? '<div class="sb">' + sub + '</div>' : '') +
         '<div class="ic">' + icon + '</div></div>';
}

// One horizontal bar row. This is the component the old dashboard was built on.
// It used to carry leads per technology. It now carries BLANKS per field.
function barRow(label, barPct, v1, v2, pct, extra) {
  let tail = '';
  if (v2 !== null && v2 !== undefined) tail += '<div class="bv sec">' + fmt(v2) + '</div>';
  if (pct !== null && pct !== undefined) {
    tail += '<div class="bv pct ' + band(pct) + '">' + pct.toFixed(0) + '%</div>';
  }
  return '<div class="br ' + (extra || '') + '"><div class="bl" title="' + label + '">' + label + '</div>' +
         '<div class="bt"><div class="bf" style="width:' + barPct.toFixed(1) +
         '%;background:var(--grad-bar)"></div></div>' +
         '<div class="bv">' + fmt(v1) + '</div>' + tail + '</div>';
}

function brandView(key) {
  const b = D.brands[key];
  if (!b) return '<div class="nd">No data for this brand.</div>';
  theme(b.accent, b.accent2);

  let rows = b.rows.slice();
  if (sort === 'worst') rows.sort((x, y) => y.blanks - x.blanks);

  // Bar length is the blank count, scaled to the worst field. The longest bar is
  // the column with the most holes in it, which is the one to go and fix.
  const mx = Math.max(...rows.map(r => r.blanks), 1);

  let html = '<div class="sr">' +
    statCard('Contacts in brand', fmt(b.records), '&#128101;', '', 'marker column filled') +
    statCard('Total blanks', fmt(b.totals.blanks), '&#9888;&#65039;', 'bad', 'across ' + rows.length + ' fields') +
    statCard('Fields filled', fmt(b.totals.filled), '&#9989;', 'good', 'of ' + fmt(b.totals.cells) + ' cells') +
    statCard('Completion', b.totals.pct.toFixed(0) + '%', '&#9889;', band(b.totals.pct), '') +
    '</div>';

  let pills = '<div class="pills">';
  if (b.marker) pills += '<span class="mkr">' + b.marker + ' is filled</span>';
  for (const [nm, n] of Object.entries(b.overlap)) {
    pills += '<span class="olt">' + fmt(n) + ' also in ' + nm + '</span>';
  }
  pills += '</div>';
  html += pills;

  const head = '<div class="br" style="margin-bottom:2px">' +
    '<div class="bch l">Field</div><div></div>' +
    '<div class="bch">Blanks</div><div class="bch">Filled</div><div class="bch">%</div></div>';

  const body = rows.map(r =>
    barRow(r.label, (r.blanks / mx) * 100, r.blanks, r.filled, r.pct)
  ).join('');

  const foot = '<div class="tr"><div class="bl">TOTAL</div><div></div>' +
    '<div class="bv">' + fmt(b.totals.blanks) + '</div>' +
    '<div class="bv sec">' + fmt(b.totals.filled) + '</div>' +
    '<div class="bv">' + b.totals.pct.toFixed(0) + '%</div></div>';

  const toggle = '<div class="mt">' +
    '<button class="' + (sort === 'config' ? 'on' : '') + '" onclick="setSort(\\'config\\')">Field order</button>' +
    '<button class="' + (sort === 'worst' ? 'on' : '') + '" onclick="setSort(\\'worst\\')">Most blanks first</button>' +
    '</div>';

  html += '<div class="pn"><div class="ph"><div class="pt">Blanks by field</div>' + toggle +
          '</div><div class="bc">' + head + body + foot + '</div></div>';
  return html;
}

function allView() {
  theme('#4338ED', '#F97316');
  const o = D.overall || {};
  const t = D.totals;
  const hasOverlap = o.regions && o.regions.length;

  let html = '<div class="sr">' +
    statCard('Unique contacts', fmt(hasOverlap ? o.unique : null), '&#128101;', '',
             hasOverlap ? fmt(o.duplicated) + ' double counted' : '') +
    statCard('Total blanks', fmt(t.blanks), '&#9888;&#65039;', 'bad', 'yet to complete') +
    statCard('Fields filled', fmt(t.filled), '&#9989;', 'good', 'of ' + fmt(t.cells) + ' cells') +
    statCard('Completion', t.pct.toFixed(0) + '%', '&#9889;', band(t.pct), '') +
    '</div>';

  // Blanks per brand, same bar component.
  const brandRows = D.order.map(k => D.brands[k]).filter(Boolean);
  const mxB = Math.max(...brandRows.map(b => b.totals.blanks), 1);
  const head = '<div class="br" style="margin-bottom:2px">' +
    '<div class="bch l">Brand</div><div></div>' +
    '<div class="bch">Blanks</div><div class="bch">Filled</div><div class="bch">%</div></div>';
  const body = brandRows.map(b =>
    barRow(b.short, (b.totals.blanks / mxB) * 100, b.totals.blanks, b.totals.filled, b.totals.pct)
  ).join('');
  html += '<div class="pn"><div class="ph"><div class="pt">Blanks by brand</div></div>' +
          '<div class="bc">' + head + body + '</div></div>';

  if (hasOverlap) {
    const cols = ['#4338ED', '#10B981', '#F59E0B', '#8B5CF6', '#6B7280', '#EF4444', '#2563EB'];
    const seg = o.regions.map((r, i) =>
      '<div class="ovseg" style="width:' + ((r.n / o.unique) * 100).toFixed(2) +
      '%;background:' + cols[i % cols.length] + '" title="' + r.label + ': ' + fmt(r.n) + '"></div>'
    ).join('');
    const mxR = Math.max(...o.regions.map(r => r.n), 1);
    const rrows = o.regions.map(r =>
      barRow(r.label, (r.n / mxR) * 100, r.n, null, null, 'wide')
    ).join('');
    const rhead = '<div class="br wide" style="margin-bottom:2px">' +
      '<div class="bch l">Region</div><div></div><div class="bch">Contacts</div>' +
      '<div></div><div></div></div>';
    html += '<div class="pn"><div class="ph"><div class="pt">Contacts shared between brands</div>' +
      '<div style="font-size:11px;color:var(--txt-s)">' + fmt(o.summed) +
      ' summed &#8594; ' + fmt(o.unique) + ' unique &#183; ' + fmt(o.in_multiple) +
      ' sit in 2+ brands</div></div>' +
      '<div class="ovbar">' + seg + '</div>' +
      '<div class="bc">' + rhead + rrows + '</div></div>';
  }
  return html;
}

function setBrand(k) { active = k; render(); }
function setSort(s) { sort = s; render(); }

function render() {
  const isAll = active === ALL;
  const b = isAll ? null : D.brands[active];

  const tabs = ['<button class="tb ' + (isAll ? 'on' : '') + '" onclick="setBrand(\\'' + ALL + '\\')">All brands</button>']
    .concat(D.order.map(k =>
      '<button class="tb ' + (active === k ? 'on' : '') + '" onclick="setBrand(\\'' + k + '\\')">' +
      D.brands[k].short + '</button>'))
    .join('');

  const mark = (b && b.logo)
    ? '<img class="brandmark" src="' + b.logo + '" alt="' + b.short + '">'
    : '';
  const title = isAll
    ? '<h1>All brands <span class="hl">Data Quality</span></h1>'
    : '<h1>' + b.short + ' <span class="hl">Data Quality</span></h1>';

  document.getElementById('app').innerHTML =
    '<div class="hdr"><div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">' +
    mark + '<div>' + title +
    '<div class="sub">Blanks per field in HubSpot &#183; updated ' + D.updated + '</div></div></div>' +
    '<div class="tg">' + tabs + '</div></div>' +
    (isAll ? allView() : brandView(active)) +
    '<div class="foot">A contact is in a brand when that brand\\'s marker column is filled. ' +
    'A blank is a tracked property that is not set. Archived contacts excluded.</div>';
}

render();
"""


def build_page(payload: dict) -> str:
    js = JS.replace("__DATA__", json.dumps(payload))
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
        f"<style>{CSS}</style></head><body>"
        "<div class='db' id='app'></div>"
        f"<script>{js}</script>"
        "</body></html>"
    )
