"""
HubSpot Data Quality Dashboard.

Counts only. For every tracked field, on every brand, the app asks HubSpot two
questions: how many contacts are in this brand, and how many of them have this
property unset. Both answers come back as the "total" on a search response, so a
portal with 450,000 contacts costs the same number of API calls as one with 450.

Brands are not a field. A contact is TCS because its e-Commerce Technologies
column is filled, BinaryWorks because Drupal Partners (CMS) is filled,
ConversionBox because ConversionBox Competitors is filled. Those are independent
columns, so a contact can sit in two brands at once. The overlap panel counts
exactly how many do.

Run locally:   streamlit run app.py
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime

import streamlit as st

import ui
from assets_loader import logo_path, logo_src
from config import (
    APP_SUBTITLE,
    APP_TITLE,
    BRAND_MODE,
    BRANDS,
    CACHE_TTL_SECONDS,
    HEADER_LOGO,
    MAX_RETRIES,
    OBJECT_LABELS,
    OBJECTS,
    REQUEST_TIMEOUT,
    SEARCH_RATE_PER_SEC,
    SHOW_OVERLAP,
    TRACKED_FIELDS,
)
from hubspot_client import HubSpotClient, HubSpotError
from metrics import (
    brand_rollup,
    collect_counts,
    collect_overlaps,
    overlap_summary,
    plan_queries,
    portfolio_kpis,
    resolve_fields,
    resolve_markers,
)

st.set_page_config(
    page_title="HubSpot Data Quality",
    page_icon="■",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()

HEADER_SRC = logo_src("logo", HEADER_LOGO) if HEADER_LOGO != "" else None
_sidebar_logo = logo_path("logo")
if _sidebar_logo:
    st.logo(str(_sidebar_logo))

MODES = ["marker", "portal", "single"]
MODE_LABELS = {
    "marker": "Marker column per brand",
    "portal": "Three portals, three tokens",
    "single": "No split (one bucket)",
}


def draw_header(badge: str, meta: str, stale: bool = False) -> None:
    ui.header(APP_TITLE, APP_SUBTITLE, badge, meta, stale=stale, logo=HEADER_SRC)


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

def load_tokens() -> dict[str, str]:
    try:
        hs = st.secrets["hubspot"]
    except Exception:
        st.error("No HubSpot credentials found.")
        st.markdown(
            "Create `.streamlit/secrets.toml` locally, or paste the same block into "
            "**Manage app, Settings, Secrets** on Streamlit Cloud:\n\n"
            "```toml\n[hubspot]\ntoken = \"pat-na1-xxxxxxxx\"\n```\n\n"
            "That is a **private app access token**, not a legacy API key. HubSpot: "
            "Settings, Integrations, Private Apps. Scopes: `crm.objects.contacts.read` "
            "and `crm.schemas.contacts.read`."
        )
        st.stop()

    mode = st.session_state.get("brand_mode", BRAND_MODE)
    if mode == "portal":
        table = hs.get("tokens", {})
        missing = [b["key"] for b in BRANDS if not table.get(b["key"])]
        if missing:
            st.error("Portal mode needs one token per brand. Missing: " + ", ".join(missing))
            st.stop()
        return {b["key"]: table[b["key"]] for b in BRANDS}

    token = hs.get("token")
    if not token:
        st.error("`[hubspot] token` is missing from secrets.")
        st.stop()
    return {b["key"]: token for b in BRANDS}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_properties(token: str, object_type: str) -> list[dict]:
    """The property schema barely changes. Cache it for a day."""
    client = HubSpotClient(token, SEARCH_RATE_PER_SEC, REQUEST_TIMEOUT, MAX_RETRIES)
    return client.list_properties(object_type)


def cache_key(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

st.session_state.setdefault("counts_cache", {})

tokens = load_tokens()
try:
    properties_by_object = {
        obj: fetch_properties(tokens[BRANDS[0]["key"]], obj) for obj in OBJECTS
    }
except HubSpotError as exc:
    st.error(str(exc))
    st.stop()

CONTACT_PROPS = properties_by_object[OBJECTS[0]]


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.markdown("### SETUP")

mode = st.sidebar.radio(
    "How brands are separated",
    options=MODES,
    index=MODES.index(st.session_state.get("brand_mode", BRAND_MODE)),
    format_func=MODE_LABELS.get,
    key="brand_mode",
)

auto_markers, marker_warnings = resolve_markers(BRANDS, CONTACT_PROPS)
active_brands = [dict(b) for b in BRANDS]
markers: dict[str, str | None] = dict(auto_markers)

if mode == "marker":
    with st.sidebar.expander("Brand setup", expanded=any(v is None for v in markers.values())):
        st.caption(
            "A contact belongs to a brand when that brand's marker column is not "
            "empty. Not a value match, a presence check."
        )
        NO_MARKER = "(no marker, brand disabled)"
        names = sorted(p["name"] for p in CONTACT_PROPS)
        labels = {p["name"]: p["label"] for p in CONTACT_PROPS}

        # format_func is captured by Streamlit and can be re-invoked after this
        # block has finished, so bind the constants as defaults rather than
        # closing over module scope. A plain closure here silently mangles the
        # label once a later block rebinds the name.
        def fmt(n, _none=NO_MARKER, _labels=labels):
            return n if n == _none else f"{_labels.get(n, n)}  ({n})"

        for brand in active_brands:
            key = brand["key"]
            options = [NO_MARKER] + names
            current = markers.get(key) or NO_MARKER
            picked = st.selectbox(
                brand["name"],
                options=options,
                index=options.index(current) if current in options else 0,
                format_func=fmt,
                key=f"marker_{key}",
                help=f"Config asks for: {brand.get('marker')}",
            )
            markers[key] = None if picked == NO_MARKER else picked

        st.caption("Paste this into config.py to make it permanent.")
        st.code(
            'BRAND_MODE = "marker"\n\nBRANDS = [\n'
            + "".join(
                f'    {{"key": "{b["key"]}", "name": "{b["name"]}", '
                f'"marker": {markers[b["key"]]!r}, "extra_rules": [], "logo": None}},\n'
                for b in active_brands
            )
            + "]\n",
            language="python",
        )

elif mode == "single":
    active_brands = [
        {"key": BRANDS[0]["key"], "name": "ALL CONTACTS", "marker": None,
         "extra_rules": [], "logo": ""}
    ]
    markers = {active_brands[0]["key"]: None}

else:  # portal
    markers = {b["key"]: None for b in active_brands}

# ---- field mapping ---------------------------------------------------------

auto_mapping, field_warnings = resolve_fields(TRACKED_FIELDS, properties_by_object, OBJECTS)

with st.sidebar.expander("Field mapping", expanded=bool(field_warnings)):
    st.caption("Auto-matched against your live portal. Override anything wrong.")
    field_mapping: dict[str, dict[str, str | None]] = {}
    NOT_TRACKED = "(not tracked)"
    for spec in TRACKED_FIELDS:
        label = spec["label"]
        field_mapping[label] = {}
        st.markdown(f"**{label}**")
        for obj in OBJECTS:
            opts = [NOT_TRACKED] + sorted(p["name"] for p in properties_by_object[obj])
            current = auto_mapping[label].get(obj) or NOT_TRACKED
            picked = st.selectbox(
                OBJECT_LABELS.get(obj, obj),
                options=opts,
                index=opts.index(current) if current in opts else 0,
                key=f"map_{label}_{obj}",
            )
            field_mapping[label][obj] = None if picked == NOT_TRACKED else picked

with st.sidebar.expander("Performance", expanded=False):
    rate = st.slider(
        "Search requests per second", 1.0, 5.0, float(SEARCH_RATE_PER_SEC), 0.5,
        help="HubSpot caps the CRM Search API at 5 per second across the whole account.",
    )
    ttl = st.number_input("Cache results for (minutes)", 1, 1440, CACHE_TTL_SECONDS // 60)
    want_overlap = st.checkbox(
        "Count contacts in more than one brand", value=SHOW_OVERLAP,
        help="Adds 4 API calls: three pairs and the triple.",
    )

refresh = st.sidebar.button("Refresh from HubSpot", width="stretch", type="primary")

for w in field_warnings:
    st.sidebar.warning(w)


# ---------------------------------------------------------------------------
# Guards, before spending any API calls
# ---------------------------------------------------------------------------

tracked_now = {
    label: per_obj
    for label, per_obj in field_mapping.items()
    if any(per_obj.get(o) for o in OBJECTS)
}
if not tracked_now:
    st.error("No fields resolved. Open Field mapping in the sidebar and pick at least one.")
    st.stop()

# A brand with no marker sends no filter, and HubSpot then returns the entire
# portal. Every tab would show the same total and every percentage would be a
# share of the whole database. That is a wrong answer wearing the costume of a
# right one, so we refuse to fetch.
if mode == "marker":
    unmapped = [b["name"] for b in active_brands if not markers.get(b["key"])]
    if unmapped:
        draw_header("NOT CONFIGURED", "marker columns unresolved", stale=True)
        asked = "".join(
            f"<li><b>{b['name']}</b> wants <code>{b.get('marker')}</code></li>"
            for b in active_brands
            if not markers.get(b["key"])
        )
        ui.alarm(
            "BRAND MARKER MISSING",
            "No marker column resolved for: <b>" + ", ".join(unmapped) + "</b>.<br><br>"
            "A brand is defined by a column being <i>filled</i>, so without one "
            "the search would carry no filter and every brand tab would count "
            "your <b>entire portal</b>. Numbers are withheld.<br><br>"
            f"<b>Config asks for:</b><ul>{asked}</ul>"
            "Those labels do not exist in this portal, or they are spelled "
            "differently. Open <b>Brand setup</b> in the sidebar and pick the real "
            "column from the dropdown."
        )
        st.stop()
    for w in marker_warnings:
        st.sidebar.warning(w)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

overlap_on = want_overlap and mode == "marker" and len(active_brands) > 1

payload = {
    "mode": mode,
    "brands": [{"k": b["key"], "x": b.get("extra_rules")} for b in active_brands],
    "markers": markers,
    "fields": tracked_now,
    "objects": OBJECTS,
    "overlap": overlap_on,
}
key = cache_key(payload)
cached = st.session_state["counts_cache"].get(key)
fresh = cached and (time.time() - cached["ts"] < ttl * 60) and not refresh

if fresh:
    df = cached["df"]
    inters = {frozenset(k): v for k, v in cached["inters"]}
    expressible = cached["expressible"]
    fetched_at = cached["ts"]
else:
    n_calls = len(plan_queries(active_brands, OBJECTS, tracked_now, with_overlap=overlap_on))
    bar = st.progress(0.0, text=f"Querying HubSpot, {n_calls} calls, about {int(n_calls / rate) + 1}s")
    clients = {
        b["key"]: HubSpotClient(tokens[b["key"]], rate, REQUEST_TIMEOUT, MAX_RETRIES)
        for b in active_brands
    }
    done = {"n": 0}

    def tick(_i: int, _t: int, note: str) -> None:
        done["n"] += 1
        bar.progress(min(done["n"] / n_calls, 1.0), text=f"{done['n']}/{n_calls}  {note}")

    try:
        df = collect_counts(
            clients=clients,
            brands=active_brands,
            objects=OBJECTS,
            field_mapping=tracked_now,
            markers=markers,
            progress_cb=tick,
        )
        inters, expressible = {}, True
        if overlap_on:
            inters, expressible = collect_overlaps(
                client=clients[active_brands[0]["key"]],
                object_type=OBJECTS[0],
                brands=active_brands,
                markers=markers,
                progress_cb=tick,
            )
    except HubSpotError as exc:
        bar.empty()
        st.error(str(exc))
        st.stop()

    bar.empty()
    fetched_at = time.time()
    st.session_state["counts_cache"][key] = {
        "df": df,
        "inters": [(tuple(sorted(k)), v) for k, v in inters.items()],
        "expressible": expressible,
        "ts": fetched_at,
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

rollup = brand_rollup(df)
summary = overlap_summary(rollup, inters) if (overlap_on and inters) else None
kpis = portfolio_kpis(df, summary)

names = {b["key"]: b["name"] for b in active_brands}
age_min = (time.time() - fetched_at) / 60
stamp = datetime.fromtimestamp(fetched_at).strftime("%d %b %Y, %H:%M")

draw_header(
    badge="LIVE" if age_min < 5 else "CACHED",
    meta=f"{len(tracked_now)} fields, {len(active_brands)} brand(s), contacts · updated {stamp}",
    stale=age_min >= 5,
)

# Post-flight: markers resolved but suspicious.
if len(active_brands) > 1 and not rollup.empty:
    counts = rollup.set_index("brand_name")["records"]
    if counts.nunique() == 1 and counts.iloc[0] > 0:
        ui.alarm(
            "EVERY BRAND RETURNED THE SAME COUNT",
            f"All {len(active_brands)} brands came back with exactly "
            f"<b>{int(counts.iloc[0]):,}</b> contacts. Different marker columns "
            "almost never have identical fill counts, so the markers are probably "
            "all pointing at the same property. Check <b>Brand setup</b>."
        )
    empty = [n for n, v in counts.items() if v == 0]
    if empty:
        ui.alarm(
            "A BRAND MATCHED ZERO CONTACTS",
            "Nothing matched for: <b>" + ", ".join(empty) + "</b>.<br><br>"
            "Either the marker column really is empty on every contact, or the "
            "wrong column was picked. Confirm the marker shown on the brand card "
            "is the one you expect."
        )

tabs = st.tabs(["OVERVIEW"] + [b["name"] for b in active_brands])

with tabs[0]:
    scope = f"across {len(active_brands)} brand(s)"
    if summary and summary["duplicated"]:
        scope = f"unique, {summary['duplicated']:,} double counted across brands"
    ui.kpi_grid(kpis, scope=scope)

    ui.section("DATA COMPLETENESS BY BRAND")
    cols = st.columns(len(active_brands), gap="small")
    for col, brand in zip(cols, active_brands):
        row = rollup[rollup["brand_key"] == brand["key"]]
        if row.empty:
            continue
        shares = None
        if summary:
            shares = [
                (names[other["key"]], int(summary["intersections"].get(
                    frozenset([brand["key"], other["key"]]), 0)))
                for other in active_brands
                if other["key"] != brand["key"]
            ]
        with col:
            ui.brand_card(
                df_brand=df[df["brand_key"] == brand["key"]],
                rollup_row=row.iloc[0],
                objects=OBJECTS,
                logo=logo_src(brand["key"], brand.get("logo")),
                shares=shares,
            )

    if overlap_on:
        ui.section("CONTACTS SHARED BETWEEN BRANDS")
        if summary:
            ui.overlap_panel(summary, names, expressible=expressible)
        else:
            ui.overlap_panel({}, names, expressible=False)

    ui.section("COMPLETION BY BRAND")
    ui.comparison_panel(rollup)
    ui.legend()
    ui.foot_note(
        "A contact is in a brand when that brand's marker column is filled "
        "(HubSpot HAS_PROPERTY), so a contact with two markers filled is counted "
        "in two brands. A blank is a tracked property that is not set "
        "(NOT_HAS_PROPERTY). Archived contacts are excluded."
    )

for tab, brand in zip(tabs[1:], active_brands):
    with tab:
        sub = df[df["brand_key"] == brand["key"]]
        row = rollup[rollup["brand_key"] == brand["key"]]
        if sub.empty or row.empty:
            st.info("No data for this brand. Check its marker column in the sidebar.")
            continue
        r = row.iloc[0]

        ui.brand_banner(brand["name"], logo_src(brand["key"], brand.get("logo")))
        if r["marker"]:
            st.caption(f"A contact is in this brand when `{r['marker']}` is not empty.")

        ui.kpi_grid(
            {
                "records": int(r["records"]),
                "blanks": int(r["blanks"]),
                "filled": int(r["filled"]),
                "completion": float(r["completion"]),
            },
            scope="contacts in " + brand["name"],
        )

        if summary:
            shared = [
                (names[o["key"]], int(summary["intersections"].get(
                    frozenset([brand["key"], o["key"]]), 0)))
                for o in active_brands
                if o["key"] != brand["key"]
            ]
            only = int(summary["regions"].get(frozenset([brand["key"]]), 0))
            bits = " · ".join(f"{n:,} also in {nm}" for nm, n in shared)
            st.caption(f"{only:,} contacts are in this brand only. {bits}")

        for obj in OBJECTS:
            obj_df = sub[sub["object"] == obj]
            if obj_df.empty:
                continue
            ui.section(OBJECT_LABELS.get(obj, obj.upper()))
            ui.field_table(obj_df)

        ui.section("WORST FIELDS FIRST")
        for _, w in sub.sort_values("completion").head(6).iterrows():
            st.markdown(
                f"**{w['field']}** · {int(w['blanks']):,} blank of {int(w['total']):,} "
                f"· {w['completion']:.0f}% complete"
            )

st.download_button(
    "Download summary CSV",
    data=df.to_csv(index=False).encode(),
    file_name=f"hubspot_data_quality_{datetime.now():%Y%m%d}.csv",
    mime="text/csv",
)
