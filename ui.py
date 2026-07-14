"""
Everything visual.

Two palettes, light and dark, selected by THEME in config.py. The structure
(KPI cards, brand cards, banded field rows, comparison bars with 70 and 90
threshold ticks) is identical in both. Only the colour variables swap.

The light palette is not the dark one inverted. Neon greens that glow against
#070b14 turn illegible on white, so the text colours are darkened and the glow
shadows on the status dots become rings instead.

Streamlit's markdown renderer treats four or more leading spaces as a code
block, so every HTML string built here is emitted without indentation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import AMBER_AT, GREEN_AT, OBJECT_LABELS, THEME

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------

PALETTES = {
    "dark": {
        "--void": "#070b14",
        "--panel": "#0d1526",
        "--border": "rgba(255,255,255,0.09)",
        "--grid": "rgba(255,255,255,0.025)",
        "--track": "rgba(255,255,255,0.07)",
        "--hair": "rgba(255,255,255,0.04)",
        "--shadow": "none",
        "--text-1": "#e8edf5",
        "--text-2": "#8291ab",
        "--text-3": "#56637d",
        "--green": "#22e08a",
        "--amber": "#ffb020",
        "--red": "#ff4d5e",
        "--cyan": "#38bdf8",
        "--fill-green": "#22e08a",
        "--fill-amber": "#ffb020",
        "--fill-red": "#ff4d5e",
        "--glow-green": "0 0 7px #22e08a",
        "--glow-amber": "0 0 7px #ffb020",
        "--glow-red": "0 0 7px #ff4d5e",
        "--badge-bg": "rgba(56,189,248,0.12)",
        "--badge-br": "rgba(56,189,248,0.35)",
        "--warn-bg": "rgba(255,77,94,0.10)",
        "--warn-br": "rgba(255,77,94,0.45)",
    },
    "light": {
        "--void": "#f6f7fb",
        "--panel": "#ffffff",
        "--border": "rgba(15,23,42,0.10)",
        "--grid": "rgba(15,23,42,0.035)",
        "--track": "rgba(15,23,42,0.08)",
        "--hair": "rgba(15,23,42,0.06)",
        "--shadow": "0 1px 2px rgba(15,23,42,0.04), 0 2px 8px rgba(15,23,42,0.05)",
        "--text-1": "#0b1220",
        "--text-2": "#5b6b85",
        "--text-3": "#8a97ab",
        "--green": "#0f9d6b",
        "--amber": "#c2740a",
        "--red": "#d81e45",
        "--cyan": "#0369a1",
        "--fill-green": "#10b981",
        "--fill-amber": "#f59e0b",
        "--fill-red": "#f43f5e",
        "--glow-green": "0 0 0 3px rgba(16,185,129,0.18)",
        "--glow-amber": "0 0 0 3px rgba(245,158,11,0.18)",
        "--glow-red": "0 0 0 3px rgba(244,63,94,0.18)",
        "--badge-bg": "rgba(3,105,161,0.08)",
        "--badge-br": "rgba(3,105,161,0.30)",
        "--warn-bg": "rgba(216,30,69,0.06)",
        "--warn-br": "rgba(216,30,69,0.35)",
    },
}


def _vars(theme: str) -> str:
    palette = PALETTES.get(theme, PALETTES["light"])
    body = "".join(f"{k}:{v};" for k, v in palette.items())
    return ":root{" + body + "}"


# Structure only. Every colour comes from a variable above, so this block is
# shared by both themes. Plain string, never an f-string: it is full of braces.
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root{
  --font-sans:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  --font-mono:'IBM Plex Mono','SF Mono','Roboto Mono','Courier New',monospace;
}

.stApp{
  background:var(--void);
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size:26px 26px;
}
html, body, [class*="css"]{font-family:var(--font-sans);color:var(--text-1);}
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1180px;}
#MainMenu, footer{visibility:hidden;}

.mono{font-family:var(--font-mono);}
.txt-g{color:var(--green);} .txt-a{color:var(--amber);} .txt-r{color:var(--red);}
.bg-green{background:var(--fill-green);} .bg-amber{background:var(--fill-amber);} .bg-red{background:var(--fill-red);}

.dq-header{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border);}
.dq-title{font-size:20px;font-weight:700;letter-spacing:1.5px;margin:0 0 5px;font-family:var(--font-mono);}
.dq-sub{font-size:12.5px;color:var(--text-2);margin:0;}
.dq-meta{text-align:right;}
.badge{display:inline-block;background:var(--badge-bg);color:var(--cyan);border:1px solid var(--badge-br);font-size:9.5px;letter-spacing:1px;font-weight:700;padding:3px 8px;border-radius:4px;margin-bottom:6px;}
.badge.stale{background:var(--warn-bg);color:var(--amber);border-color:var(--warn-br);}
.dq-meta-sub{font-size:10.5px;color:var(--text-3);}
.hdr-id{display:flex;align-items:center;gap:14px;}
.hdr-logo{height:32px;max-width:170px;width:auto;object-fit:contain;display:block;}

.alarm{background:var(--warn-bg);border:1px solid var(--warn-br);border-left:4px solid var(--red);border-radius:10px;padding:14px 18px;margin-bottom:20px;}
.alarm-title{font-family:var(--font-mono);font-size:12px;font-weight:700;letter-spacing:1px;color:var(--red);margin-bottom:6px;}
.alarm-body{font-size:12.5px;color:var(--text-1);line-height:1.6;}
.alarm-body code{font-family:var(--font-mono);background:var(--track);padding:1px 5px;border-radius:3px;font-size:11.5px;}

.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px;}
.kpi-card{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--border);border-radius:10px;padding:14px 16px;box-shadow:var(--shadow);}
.kpi-card.k-cyan{border-left-color:var(--cyan);}
.kpi-card.k-red{border-left-color:var(--fill-red);}
.kpi-card.k-green{border-left-color:var(--fill-green);}
.kpi-card.k-amber{border-left-color:var(--fill-amber);}
.kpi-label{font-size:10px;color:var(--text-2);letter-spacing:1px;margin-bottom:8px;}
.kpi-value{font-size:26px;font-weight:700;font-family:var(--font-mono);}
.kpi-sub{font-size:11px;color:var(--text-3);margin-top:4px;}
.kpi-bar-track{height:5px;background:var(--track);border-radius:3px;margin-top:10px;overflow:hidden;}
.kpi-bar-fill{height:100%;border-radius:3px;}

.section-label{font-size:11px;letter-spacing:1.5px;color:var(--text-2);font-weight:700;margin:6px 0 12px;display:flex;align-items:center;gap:8px;}
.section-label::after{content:'';flex:1;height:1px;background:var(--border);}

.brand-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:24px;}
.brand-card{background:var(--panel);border:1px solid var(--border);border-top:3px solid var(--border);border-radius:12px;padding:16px;box-shadow:var(--shadow);}
.brand-card.edge-amber{border-top-color:var(--fill-amber);}
.brand-card.edge-red{border-top-color:var(--fill-red);}
.brand-card.edge-green{border-top-color:var(--fill-green);}
.brand-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border);}
.brand-id{display:flex;align-items:center;gap:10px;min-width:0;}
.brand-logo{height:24px;max-width:140px;width:auto;object-fit:contain;flex-shrink:0;display:block;}
.brand-meta{min-width:0;}
.brand-name{font-size:12px;font-weight:700;letter-spacing:0.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.brand-count{font-size:10px;color:var(--text-3);font-family:var(--font-mono);margin-top:2px;}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex-shrink:0;}
.dot.green{background:var(--fill-green);box-shadow:var(--glow-green);}
.dot.amber{background:var(--fill-amber);box-shadow:var(--glow-amber);}
.dot.red{background:var(--fill-red);box-shadow:var(--glow-red);animation:pulse-red 2s ease-in-out infinite;}
@keyframes pulse-red{0%,100%{opacity:1;}50%{opacity:0.45;}}
@media (prefers-reduced-motion:reduce){.dot.red{animation:none;}}

.obj-tag{font-size:8.5px;letter-spacing:1px;color:var(--text-3);font-weight:700;margin:10px 0 4px;}
.field-head-row{display:grid;grid-template-columns:1fr 52px 46px 40px 56px;font-size:9px;color:var(--text-3);letter-spacing:0.5px;padding-bottom:6px;margin-bottom:2px;border-bottom:1px solid var(--border);}
.field-head-row span:not(:first-child){text-align:right;}
.field-row{display:grid;grid-template-columns:1fr 52px 46px 40px 56px;align-items:center;gap:6px;padding:6px 0;font-size:11.5px;border-top:1px solid var(--hair);}
.field-name{color:var(--text-1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.field-total{text-align:right;color:var(--text-3);font-family:var(--font-mono);}
.field-blank{text-align:right;color:var(--text-2);font-family:var(--font-mono);}
.field-pct{text-align:right;font-weight:700;font-size:11px;font-family:var(--font-mono);}
.mini-track{height:4px;background:var(--track);border-radius:2px;overflow:hidden;}
.mini-fill{height:100%;border-radius:2px;}

.brand-foot{display:flex;justify-content:space-between;align-items:flex-end;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);}
.bf-label{font-size:9px;color:var(--text-3);letter-spacing:0.5px;margin-bottom:3px;}
.bf-value{font-size:18px;font-weight:700;font-family:var(--font-mono);}

.compare-wrap{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px 20px;margin-bottom:18px;box-shadow:var(--shadow);}
.compare-row{display:grid;grid-template-columns:160px 1fr 46px;align-items:center;gap:12px;padding:10px 0;font-size:12px;}
.compare-track{position:relative;height:10px;background:var(--track);border-radius:5px;}
.compare-fill{height:100%;border-radius:5px;}
.tick{position:absolute;top:-3px;height:16px;width:1px;background:var(--text-3);opacity:0.55;}
.compare-pct{text-align:right;font-weight:700;font-family:var(--font-mono);}
.gauge-key{display:flex;justify-content:flex-end;gap:14px;font-size:9px;color:var(--text-3);margin-top:12px;}

.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;color:var(--text-2);justify-content:center;margin-top:4px;}
.legend span{display:flex;align-items:center;gap:6px;}
.legend .dot.red{animation:none;}

.foot-note{text-align:center;font-size:10.5px;color:var(--text-3);margin-top:22px;}

.tab-id{display:flex;align-items:center;gap:14px;margin:4px 0 18px;}
.tab-logo{height:32px;max-width:190px;width:auto;object-fit:contain;display:block;}
.tab-name{font-size:15px;font-weight:700;letter-spacing:1px;font-family:var(--font-mono);}

.dq-table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:var(--shadow);margin-bottom:8px;}
.dq-table th{font-size:9.5px;letter-spacing:1px;color:var(--text-3);font-weight:700;text-align:left;padding:11px 14px;border-bottom:1px solid var(--border);background:var(--void);}
.dq-table th.num{text-align:right;}
.dq-table td{font-size:12.5px;padding:10px 14px;border-top:1px solid var(--hair);color:var(--text-1);vertical-align:middle;}
.dq-table td.num{text-align:right;font-family:var(--font-mono);}
.dq-table td.prop{font-family:var(--font-mono);font-size:11.5px;color:var(--text-2);}
.dq-table td.pct{font-family:var(--font-mono);font-weight:700;text-align:right;width:52px;}
.dq-table td.bar{width:130px;}
.dq-table tr:first-child td{border-top:none;}

.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{background:transparent;color:var(--text-2);font-family:var(--font-mono);font-size:11px;letter-spacing:1px;font-weight:600;padding:8px 14px;}
.stTabs [aria-selected="true"]{color:var(--cyan);}
"""

CSS = "<style>" + _vars(THEME) + BASE_CSS + "</style>"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def band(pct: float) -> str:
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


def alarm(title: str, body_html: str) -> None:
    """Loud, unmissable banner. Used when the numbers cannot be trusted."""
    _html(
        '<div class="alarm">'
        f'<div class="alarm-title">{title}</div>'
        f'<div class="alarm-body">{body_html}</div>'
        "</div>"
    )


def kpi_grid(kpis: dict, scope: str = "") -> None:
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
        if len(objects) > 1:
            body.append(f'<div class="obj-tag">{OBJECT_LABELS.get(obj, obj.upper())}</div>')
        body.append(HEAD_ROW)
        body.append(_field_rows(sub))

    mark = (
        f'<img class="brand-logo" src="{logo}" alt="{rollup_row["brand_name"]}">'
        if logo
        else f'<span class="dot {b}"></span>'
    )

    _html(
        f'<div class="brand-card edge-{b}">'
        '<div class="brand-head">'
        f'<div class="brand-id">{mark}'
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
    mark = f'<img class="tab-logo" src="{logo}" alt="{name}">' if logo else ""
    _html(f'<div class="tab-id">{mark}<div class="tab-name">{name}</div></div>')


def field_table(df_obj: pd.DataFrame) -> None:
    """
    Detail table for a brand tab.

    Deliberately hand-rolled instead of st.dataframe with a ProgressColumn:
    that widget paints every bar in the theme's primary colour, so a field at
    98% and a field at 37% look identical. Here the bar carries the same
    green / amber / red banding as the cards, which is the entire point.
    """
    rows = []
    for _, r in df_obj.iterrows():
        b = band(r["completion"])
        rows.append(
            "<tr>"
            f'<td>{r["field"]}</td>'
            f'<td class="prop">{r["property"]}</td>'
            f'<td class="num">{_n(r["total"])}</td>'
            f'<td class="num {_txt(b)}">{_n(r["blanks"])}</td>'
            f'<td class="num">{_n(r["filled"])}</td>'
            f'<td class="bar"><div class="mini-track"><div class="mini-fill {_bg(b)}" '
            f'style="width:{r["completion"]:.0f}%"></div></div></td>'
            f'<td class="pct {_txt(b)}">{r["completion"]:.0f}%</td>'
            "</tr>"
        )
    _html(
        '<table class="dq-table"><thead><tr>'
        "<th>FIELD</th><th>HUBSPOT PROPERTY</th>"
        '<th class="num">TOTAL</th><th class="num">BLANKS</th><th class="num">FILLED</th>'
        '<th colspan="2">COMPLETION</th>'
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


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
