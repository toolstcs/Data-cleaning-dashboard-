"""
Everything visual. The CSS is lifted straight from the HTML framework so the
Streamlit build looks identical: same void background, same IBM Plex pairing,
same green / amber / red banding, same 70 and 90 threshold ticks.

Streamlit's markdown renderer treats four or more leading spaces as a code
block, so every HTML string built here is emitted without indentation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import AMBER_AT, GREEN_AT, OBJECT_LABELS

# CSS lives in a plain string, never an f-string, because it is full of braces.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root{
  --void:#070b14;
  --panel:#0d1526;
  --border:rgba(255,255,255,0.09);
  --text-1:#e8edf5;
  --text-2:#8291ab;
  --text-3:#56637d;
  --green:#22e08a;
  --amber:#ffb020;
  --red:#ff4d5e;
  --cyan:#38bdf8;
  --font-sans:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  --font-mono:'IBM Plex Mono','SF Mono','Roboto Mono','Courier New',monospace;
}

.stApp{
  background:var(--void);
  background-image:
    linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size:26px 26px;
}
html, body, [class*="css"]{font-family:var(--font-sans);color:var(--text-1);}
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1180px;}
#MainMenu, footer{visibility:hidden;}

.mono{font-family:var(--font-mono);}
.txt-g{color:var(--green);} .txt-a{color:var(--amber);} .txt-r{color:var(--red);}
.bg-green{background:var(--green);} .bg-amber{background:var(--amber);} .bg-red{background:var(--red);}

.dq-header{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border);}
.dq-title{font-size:20px;font-weight:700;letter-spacing:1.5px;margin:0 0 5px;font-family:var(--font-mono);}
.dq-sub{font-size:12.5px;color:var(--text-2);margin:0;}
.dq-meta{text-align:right;}
.badge{display:inline-block;background:rgba(56,189,248,0.12);color:var(--cyan);border:1px solid rgba(56,189,248,0.35);font-size:9.5px;letter-spacing:1px;font-weight:700;padding:3px 8px;border-radius:4px;margin-bottom:6px;}
.badge.stale{background:rgba(255,176,32,0.12);color:var(--amber);border-color:rgba(255,176,32,0.35);}
.dq-meta-sub{font-size:10.5px;color:var(--text-3);}

.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px;}
.kpi-card{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--border);border-radius:10px;padding:14px 16px;}
.kpi-card.k-cyan{border-left-color:var(--cyan);}
.kpi-card.k-red{border-left-color:var(--red);}
.kpi-card.k-green{border-left-color:var(--green);}
.kpi-card.k-amber{border-left-color:var(--amber);}
.kpi-label{font-size:10px;color:var(--text-2);letter-spacing:1px;margin-bottom:8px;}
.kpi-value{font-size:26px;font-weight:700;font-family:var(--font-mono);}
.kpi-sub{font-size:11px;color:var(--text-3);margin-top:4px;}
.kpi-bar-track{height:5px;background:rgba(255,255,255,0.07);border-radius:3px;margin-top:10px;overflow:hidden;}
.kpi-bar-fill{height:100%;border-radius:3px;}

.section-label{font-size:11px;letter-spacing:1.5px;color:var(--text-2);font-weight:700;margin:6px 0 12px;display:flex;align-items:center;gap:8px;}
.section-label::after{content:'';flex:1;height:1px;background:var(--border);}

.brand-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:24px;}
.brand-card{background:var(--panel);border:1px solid var(--border);border-top:3px solid var(--border);border-radius:12px;padding:16px;}
.brand-card.edge-amber{border-top-color:var(--amber);}
.brand-card.edge-red{border-top-color:var(--red);}
.brand-card.edge-green{border-top-color:var(--green);}
.brand-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border);}
.brand-id{display:flex;align-items:center;gap:10px;min-width:0;}
.brand-logo{height:26px;max-width:110px;width:auto;object-fit:contain;flex-shrink:0;display:block;}
.brand-meta{min-width:0;}
.brand-name{font-size:12.5px;font-weight:700;letter-spacing:0.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.brand-count{font-size:10px;color:var(--text-3);font-family:var(--font-mono);margin-top:2px;}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex-shrink:0;}
.dot.green{background:var(--green);box-shadow:0 0 7px var(--green);}
.dot.amber{background:var(--amber);box-shadow:0 0 7px var(--amber);}
.dot.red{background:var(--red);box-shadow:0 0 7px var(--red);animation:pulse-red 2s ease-in-out infinite;}
@keyframes pulse-red{0%,100%{box-shadow:0 0 7px var(--red);}50%{box-shadow:0 0 15px var(--red),0 0 4px var(--red);}}
@media (prefers-reduced-motion:reduce){.dot.red{animation:none;}}

.hdr-id{display:flex;align-items:center;gap:12px;}
.hdr-logo{height:34px;max-width:150px;width:auto;object-fit:contain;display:block;}
.tab-id{display:flex;align-items:center;gap:12px;margin:2px 0 16px;}
.tab-logo{height:34px;max-width:150px;width:auto;object-fit:contain;display:block;}
.tab-name{font-size:15px;font-weight:700;letter-spacing:1px;font-family:var(--font-mono);}

.obj-tag{font-size:8.5px;letter-spacing:1px;color:var(--text-3);font-weight:700;margin:10px 0 4px;}
.field-head-row{display:grid;grid-template-columns:1fr 52px 46px 40px 56px;font-size:9px;color:var(--text-3);letter-spacing:0.5px;padding-bottom:6px;margin-bottom:2px;border-bottom:1px solid var(--border);}
.field-head-row span:not(:first-child){text-align:right;}
.field-row{display:grid;grid-template-columns:1fr 52px 46px 40px 56px;align-items:center;gap:6px;padding:6px 0;font-size:11.5px;border-top:1px solid rgba(255,255,255,0.04);}
.field-name{color:var(--text-1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.field-total{text-align:right;color:var(--text-3);font-family:var(--font-mono);}
.field-blank{text-align:right;color:var(--text-2);font-family:var(--font-mono);}
.field-pct{text-align:right;font-weight:700;font-size:11px;font-family:var(--font-mono);}
.mini-track{height:4px;background:rgba(255,255,255,0.07);border-radius:2px;overflow:hidden;}
.mini-fill{height:100%;border-radius:2px;}

.brand-foot{display:flex;justify-content:space-between;align-items:flex-end;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);}
.bf-label{font-size:9px;color:var(--text-3);letter-spacing:0.5px;margin-bottom:3px;}
.bf-value{font-size:18px;font-weight:700;font-family:var(--font-mono);}

.compare-wrap{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px 20px;margin-bottom:18px;}
.compare-row{display:grid;grid-template-columns:160px 1fr 46px;align-items:center;gap:12px;padding:10px 0;font-size:12px;}
.compare-track{position:relative;height:10px;background:rgba(255,255,255,0.07);border-radius:5px;}
.compare-fill{height:100%;border-radius:5px;}
.tick{position:absolute;top:-3px;height:16px;width:1px;background:rgba(255,255,255,0.28);}
.compare-pct{text-align:right;font-weight:700;font-family:var(--font-mono);}
.gauge-key{display:flex;justify-content:flex-end;gap:14px;font-size:9px;color:var(--text-3);margin-top:12px;}

.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;color:var(--text-2);justify-content:center;margin-top:4px;}
.legend span{display:flex;align-items:center;gap:6px;}
.legend .dot.red{animation:none;}

.foot-note{text-align:center;font-size:10.5px;color:var(--text-3);margin-top:22px;}

.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{background:transparent;color:var(--text-2);font-family:var(--font-mono);font-size:11px;letter-spacing:1px;font-weight:600;padding:8px 14px;}
.stTabs [aria-selected="true"]{color:var(--cyan);}
</style>
"""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def band(pct: float) -> str:
    """green / amber / red."""
    if pct >= GREEN_AT:
        return "green"
    if pct >= AMBER_AT:
        return "amber"
    return "red"


def _txt(b: str) -> str:
    return {"green": "txt-g", "amber": "txt-a", "red": "txt-r"}[b]


def _bg(b: str) -> str:
    return {"green": "bg-green", "amber": "bg-amber", "red": "bg-red"}[b]


def _n(value) -> str:
    return f"{int(value):,}"


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# blocks
# ---------------------------------------------------------------------------

def header(
    title: str,
    subtitle: str,
    badge: str,
    meta: str,
    stale: bool = False,
    logo: str | None = None,
) -> None:
    cls = "badge stale" if stale else "badge"
    mark = f'<img class="hdr-logo" src="{logo}" alt="">' if logo else ""
    _html(
        '<div class="dq-header">'
        f'<div class="hdr-id">{mark}<div>'
        f'<div class="dq-title">{title}</div>'
        f'<p class="dq-sub">{subtitle}</p>'
        "</div></div>"
        '<div class="dq-meta">'
        f'<div class="{cls}">{badge}</div>'
        f'<div class="dq-meta-sub">{meta}</div>'
        "</div></div>"
    )


def kpi_grid(kpis: dict, scope: str = "across 3 brands") -> None:
    b = band(kpis["completion"])
    _html(
        '<div class="kpi-grid">'
        '<div class="kpi-card k-cyan">'
        '<div class="kpi-label">TOTAL RECORDS</div>'
        f'<div class="kpi-value">{_n(kpis["records"])}</div>'
        f'<div class="kpi-sub">{scope}</div>'
        "</div>"
        '<div class="kpi-card k-red">'
        '<div class="kpi-label">TOTAL BLANKS</div>'
        f'<div class="kpi-value txt-r">{_n(kpis["blanks"])}</div>'
        '<div class="kpi-sub">yet to complete</div>'
        "</div>"
        '<div class="kpi-card k-green">'
        '<div class="kpi-label">TOTAL COMPLETED</div>'
        f'<div class="kpi-value txt-g">{_n(kpis["filled"])}</div>'
        '<div class="kpi-sub">fields filled</div>'
        "</div>"
        f'<div class="kpi-card k-{b}">'
        '<div class="kpi-label">OVERALL COMPLETION</div>'
        f'<div class="kpi-value {_txt(b)}">{kpis["completion"]:.0f}%</div>'
        f'<div class="kpi-bar-track"><div class="kpi-bar-fill {_bg(b)}" style="width:{kpis["completion"]:.0f}%"></div></div>'
        "</div>"
        "</div>"
    )


def _field_rows(df_obj: pd.DataFrame) -> str:
    rows = []
    for _, r in df_obj.iterrows():
        b = band(r["completion"])
        rows.append(
            '<div class="field-row">'
            f'<span class="field-name" title="{r["property"]}">{r["field"]}</span>'
            f'<span class="field-total">{_n(r["total"])}</span>'
            f'<span class="field-blank">{_n(r["blanks"])}</span>'
            f'<span class="field-pct {_txt(b)}">{r["completion"]:.0f}%</span>'
            f'<div class="mini-track"><div class="mini-fill {_bg(b)}" style="width:{r["completion"]:.0f}%"></div></div>'
            "</div>"
        )
    return "".join(rows)


HEAD_ROW = (
    '<div class="field-head-row"><span>FIELD</span><span>TOTAL</span>'
    "<span>BLANK</span><span>%</span><span></span></div>"
)


def brand_card(
    df_brand: pd.DataFrame,
    rollup_row: pd.Series,
    objects: list[str],
    logo: str | None = None,
) -> None:
    completion = float(rollup_row["completion"])
    b = band(completion)

    body = []
    for obj in objects:
        sub = df_brand[df_brand["object"] == obj]
        if sub.empty:
            continue
        # With a single object the tag would just say CONTACTS three times.
        if len(objects) > 1:
            body.append(f'<div class="obj-tag">{OBJECT_LABELS.get(obj, obj.upper())}</div>')
        body.append(HEAD_ROW)
        body.append(_field_rows(sub))

    if logo:
        mark = f'<img class="brand-logo" src="{logo}" alt="{rollup_row["brand_name"]}">'
    else:
        mark = f'<span class="dot {b}"></span>'

    _html(
        f'<div class="brand-card edge-{b}">'
        '<div class="brand-head">'
        '<div class="brand-id">'
        f"{mark}"
        '<div class="brand-meta">'
        f'<div class="brand-name">{rollup_row["brand_name"]}</div>'
        f'<div class="brand-count">{_n(rollup_row["records"])} records</div>'
        "</div></div>"
        f'<span class="dot {b}"></span>'
        "</div>"
        + "".join(body)
        + '<div class="brand-foot">'
        f'<div><div class="bf-label">TOTAL BLANKS</div><div class="bf-value {_txt(b)}">{_n(rollup_row["blanks"])}</div></div>'
        f'<div style="text-align:right;"><div class="bf-label">COMPLETION</div><div class="bf-value {_txt(b)}">{completion:.0f}%</div></div>'
        "</div></div>"
    )


def brand_banner(name: str, logo: str | None) -> None:
    """Logo plus name strip at the top of a per-brand tab."""
    mark = f'<img class="tab-logo" src="{logo}" alt="{name}">' if logo else ""
    _html(f'<div class="tab-id">{mark}<div class="tab-name">{name}</div></div>')


def comparison_panel(rollup: pd.DataFrame) -> None:
    rows = []
    for _, r in rollup.iterrows():
        pct = float(r["completion"])
        b = band(pct)
        rows.append(
            '<div class="compare-row">'
            f'<span>{r["brand_name"]}</span>'
            '<div class="compare-track">'
            f'<div class="compare-fill {_bg(b)}" style="width:{pct:.0f}%"></div>'
            f'<div class="tick" style="left:{AMBER_AT}%"></div>'
            f'<div class="tick" style="left:{GREEN_AT}%"></div>'
            "</div>"
            f'<span class="compare-pct {_txt(b)}">{pct:.0f}%</span>'
            "</div>"
        )
    _html(
        '<div class="compare-wrap">'
        + "".join(rows)
        + '<div class="gauge-key">'
        f"<span>| {AMBER_AT}% threshold</span><span>| {GREEN_AT}% threshold</span>"
        "</div></div>"
    )


def legend() -> None:
    _html(
        '<div class="legend">'
        f'<span><span class="dot green"></span>{GREEN_AT}% or more complete</span>'
        f'<span><span class="dot amber"></span>{AMBER_AT}% to {GREEN_AT - 1}% complete</span>'
        f'<span><span class="dot red"></span>under {AMBER_AT}% complete, priority cleanup</span>'
        "</div>"
    )


def section(label: str) -> None:
    _html(f'<div class="section-label">{label}</div>')


def foot_note(text: str) -> None:
    _html(f'<p class="foot-note">{text}</p>')
