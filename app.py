"""
HubSpot Data Quality Dashboard.

Counts only. For every tracked field, on every brand, on contacts and
companies, the app asks HubSpot two questions: how many records are there, and
how many of them have this property unset. Both answers come back as the
"total" on a search response, so a portal with 300,000 contacts costs exactly
the same number of API calls as one with 300.

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
    HEADER_LOGO,
    APP_SUBTITLE,
    APP_TITLE,
    BRAND_MODE,
    BRAND_PROPERTY,
    BRANDS,
    CACHE_TTL_SECONDS,
    MAX_RETRIES,
    OBJECT_LABELS,
    OBJECTS,
    REQUEST_TIMEOUT,
    SEARCH_RATE_PER_SEC,
    TRACKED_FIELDS,
)
from hubspot_client import HubSpotClient, HubSpotError
from metrics import brand_rollup, collect_counts, plan_queries, portfolio_kpis, resolve_fields

st.set_page_config(
    page_title="HubSpot Data Quality",
    page_icon="■",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()

# Dashboard-wide mark. assets/logo.svg by default, overridable in config.
HEADER_SRC = logo_src("logo", HEADER_LOGO) if HEADER_LOGO != "" else None
_sidebar_logo = logo_path("logo")
if _sidebar_logo:
    st.logo(str(_sidebar_logo))


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

def load_tokens() -> dict[str, str]:
    """
    Returns {brand_key: token}.

    In property and single mode every brand shares one token. In portal mode
    each brand gets its own, read from [hubspot.tokens] in secrets.
    """
    try:
        hs = st.secrets["hubspot"]
    except Exception:
        st.error("No HubSpot credentials found.")
        st.markdown(
            "Create `.streamlit/secrets.toml` (locally) or paste the same block into "
            "**Manage app, Settings, Secrets** on Streamlit Cloud:\n\n"
            "```toml\n[hubspot]\ntoken = \"pat-na1-xxxxxxxx\"\n```\n\n"
            "The token is a **private app access token**, not a legacy API key. "
            "HubSpot: Settings, Integrations, Private Apps, Create private app. "
            "Scopes needed: `crm.objects.contacts.read`, `crm.objects.companies.read`, "
            "`crm.schemas.contacts.read`, `crm.schemas.companies.read`."
        )
        st.stop()

    mode = st.session_state.get("brand_mode", BRAND_MODE)

    if mode == "portal":
        table = hs.get("tokens", {})
        missing = [b["key"] for b in BRANDS if not table.get(b["key"])]
        if missing:
            st.error(
                "Portal mode needs one token per brand. Missing in secrets: "
                + ", ".join(missing)
            )
            st.stop()
        return {b["key"]: table[b["key"]] for b in BRANDS}

    token = hs.get("token")
    if not token:
        st.error("`[hubspot] token` is missing from secrets.")
        st.stop()
    return {b["key"]: token for b in BRANDS}


# ---------------------------------------------------------------------------
# Cached reads
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_properties(token: str, object_type: str) -> list[dict]:
    """Property schema barely changes. Cache it for a day."""
    client = HubSpotClient(token, SEARCH_RATE_PER_SEC, REQUEST_TIMEOUT, MAX_RETRIES)
    return client.list_properties(object_type)


def counts_cache_key(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

# Note: brand_mode is NOT setdefault-ed here. It is owned by the sidebar radio
# widget below (key="brand_mode"). Writing it before the widget exists makes
# Streamlit complain about a default clashing with session state.
st.session_state.setdefault("counts_cache", {})

tokens = load_tokens()

try:
    properties_by_object = {
        obj: fetch_properties(tokens[BRANDS[0]["key"]], obj) for obj in OBJECTS
    }
except HubSpotError as exc:
    st.error(str(exc))
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar: brand setup, field mapping, performance
# ---------------------------------------------------------------------------

st.sidebar.markdown("### SETUP")

mode = st.sidebar.radio(
    "How brands are separated",
    options=["property", "portal", "single"],
    index=["property", "portal", "single"].index(
        st.session_state.get("brand_mode", BRAND_MODE)
    ),
    format_func={
        "property": "One portal, brand property",
        "portal": "Three portals, three tokens",
        "single": "No split (one bucket)",
    }.get,
    key="brand_mode",
)

# ---- brand property picker -------------------------------------------------

active_brand_property: dict[str, str | None] = {obj: None for obj in OBJECTS}
active_brands = [dict(b) for b in BRANDS]

if mode == "property":
    with st.sidebar.expander("Brand setup", expanded=False):
        st.caption(
            "Pick the property that says which brand a record belongs to, then "
            "tick the values that map to each brand."
        )

        # Candidates: properties that exist on the object, brand-ish ones first.
        def _score(prop: dict) -> tuple:
            hint = f"{prop['name']} {prop['label']}".lower()
            keyword = any(
                k in hint
                for k in ("brand", "business unit", "business_unit", "portal", "division", "company brand")
            )
            enum = prop.get("fieldType") in ("select", "radio", "checkbox", "booleancheckbox")
            return (0 if keyword else 1, 0 if enum else 1, prop["label"].lower())

        # One picker per configured object. With OBJECTS = ["contacts"] that is
        # a single picker, and the loop still holds if companies come back.
        ranked: dict[str, list[dict]] = {}
        for obj in OBJECTS:
            ranked[obj] = sorted(properties_by_object[obj], key=_score)
            names = [p["name"] for p in ranked[obj]]
            if not names:
                continue
            default_name = BRAND_PROPERTY.get(obj)
            default_idx = names.index(default_name) if default_name in names else 0
            label = (
                "Brand property"
                if len(OBJECTS) == 1
                else f"Brand property ({OBJECT_LABELS.get(obj, obj).lower()})"
            )
            active_brand_property[obj] = st.selectbox(
                label,
                options=names,
                index=default_idx,
                format_func=lambda n, o=obj: next(
                    (f"{p['label']}  ({p['name']})" for p in ranked[o] if p["name"] == n), n
                ),
                key=f"brand_prop_{obj}",
            )

        # Value list comes off the first object's chosen property.
        first = OBJECTS[0]
        chosen = active_brand_property[first]
        options = next(
            (p["options"] for p in ranked.get(first, []) if p["name"] == chosen), []
        )
        st.caption(
            f"{len(options)} value(s) defined on this property."
            if options
            else "This property is free text, so type the values by hand."
        )

        for brand in active_brands:
            if options:
                brand["values"] = st.multiselect(
                    brand["name"],
                    options=options,
                    default=[v for v in brand.get("values", []) if v in options],
                    key=f"vals_{brand['key']}",
                )
            else:
                raw = st.text_input(
                    brand["name"],
                    value=", ".join(str(v) for v in brand.get("values", [])),
                    key=f"vals_{brand['key']}",
                    help="Comma separated. Up to 5 values.",
                )
                brand["values"] = [v.strip() for v in raw.split(",") if v.strip()]

        snippet = (
            'BRAND_MODE = "property"\n\n'
            "BRAND_PROPERTY = {\n"
            + "".join(
                f'    "{obj}": "{active_brand_property[obj]}",\n'
                for obj in OBJECTS
                if active_brand_property.get(obj)
            )
            + "}\n\n"
            "BRANDS = [\n"
            + "".join(
                f'    {{"key": "{b["key"]}", "name": "{b["name"]}", '
                f'"values": {b["values"]!r}, "logo": {b.get("logo")!r}}},\n'
                for b in active_brands
            )
            + "]\n"
        )
        st.caption("Paste this into config.py to make it permanent.")
        st.code(snippet, language="python")

elif mode == "single":
    active_brands = [
        {"key": BRANDS[0]["key"], "name": "ALL RECORDS", "values": [], "logo": ""}
    ]

# ---- field mapping ---------------------------------------------------------

auto_mapping, warnings = resolve_fields(TRACKED_FIELDS, properties_by_object, OBJECTS)

with st.sidebar.expander("Field mapping", expanded=bool(warnings)):
    st.caption(
        "Auto-matched against your live portal. Override anything that looks wrong."
    )
    field_mapping: dict[str, dict[str, str | None]] = {}
    NONE = "(not tracked)"

    for spec in TRACKED_FIELDS:
        label = spec["label"]
        field_mapping[label] = {}
        st.markdown(f"**{label}**")
        for obj in OBJECTS:
            opts = [NONE] + sorted(p["name"] for p in properties_by_object[obj])
            current = auto_mapping[label].get(obj) or NONE
            idx = opts.index(current) if current in opts else 0
            picked = st.selectbox(
                OBJECT_LABELS.get(obj, obj),
                options=opts,
                index=idx,
                key=f"map_{label}_{obj}",
            )
            field_mapping[label][obj] = None if picked == NONE else picked

# ---- performance -----------------------------------------------------------

with st.sidebar.expander("Performance", expanded=False):
    rate = st.slider(
        "Search requests per second",
        min_value=1.0,
        max_value=5.0,
        value=float(SEARCH_RATE_PER_SEC),
        step=0.5,
        help=(
            "HubSpot caps the CRM Search API at 5 per second across the whole "
            "account. Keep headroom if other integrations share the portal."
        ),
    )
    ttl = st.number_input(
        "Cache results for (minutes)",
        min_value=1,
        max_value=1440,
        value=CACHE_TTL_SECONDS // 60,
    )

refresh = st.sidebar.button("Refresh from HubSpot", width="stretch", type="primary")

for w in warnings:
    st.sidebar.warning(w)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

tracked_now = {
    label: per_obj
    for label, per_obj in field_mapping.items()
    if any(per_obj.get(o) for o in OBJECTS)
}

if not tracked_now:
    st.error("No fields resolved. Open Field mapping in the sidebar and pick at least one.")
    st.stop()

if mode == "property" and not any(b["values"] for b in active_brands):
    st.warning(
        "No brand values are mapped yet, so every brand would return the same "
        "numbers. Open Brand setup in the sidebar, or switch to 'No split'."
    )

plan_payload = {
    "mode": mode,
    "brands": [{"k": b["key"], "v": b["values"]} for b in active_brands],
    "brand_property": active_brand_property,
    "fields": tracked_now,
    "objects": OBJECTS,
}
key = counts_cache_key(plan_payload)
cached = st.session_state["counts_cache"].get(key)
fresh = cached and (time.time() - cached["ts"] < ttl * 60) and not refresh

if fresh:
    df = cached["df"]
    fetched_at = cached["ts"]
else:
    n_calls = len(plan_queries(active_brands, OBJECTS, tracked_now))
    eta = int(n_calls / rate) + 1
    bar = st.progress(0.0, text=f"Querying HubSpot, {n_calls} calls, about {eta}s")

    clients = {
        b["key"]: HubSpotClient(tokens[b["key"]], rate, REQUEST_TIMEOUT, MAX_RETRIES)
        for b in active_brands
    }

    def _tick(done: int, total: int, note: str) -> None:
        bar.progress(done / total, text=f"{done}/{total}  {note}")

    try:
        df = collect_counts(
            clients=clients,
            brands=active_brands,
            objects=OBJECTS,
            field_mapping=tracked_now,
            brand_property=active_brand_property,
            progress_cb=_tick,
        )
    except HubSpotError as exc:
        bar.empty()
        st.error(str(exc))
        st.stop()

    bar.empty()
    fetched_at = time.time()
    st.session_state["counts_cache"][key] = {"df": df, "ts": fetched_at}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

rollup = brand_rollup(df)
kpis = portfolio_kpis(df)

age_min = (time.time() - fetched_at) / 60
stamp = datetime.fromtimestamp(fetched_at).strftime("%d %b %Y, %H:%M")

ui.header(
    title=APP_TITLE,
    subtitle=APP_SUBTITLE,
    badge="LIVE" if age_min < 5 else "CACHED",
    meta=(
        f"{len(tracked_now)} fields, {len(active_brands)} brand(s), "
        f"{', '.join(OBJECT_LABELS.get(o, o).lower() for o in OBJECTS)} "
        f"· updated {stamp}"
    ),
    stale=age_min >= 5,
    logo=HEADER_SRC,
)

tab_labels = ["OVERVIEW"] + [b["name"] for b in active_brands]
tabs = st.tabs(tab_labels)

# ---- overview --------------------------------------------------------------

with tabs[0]:
    ui.kpi_grid(kpis, scope=f"across {len(active_brands)} brand(s)")

    ui.section("DATA COMPLETENESS BY BRAND")
    cols = st.columns(len(active_brands), gap="small")
    for col, brand in zip(cols, active_brands):
        row = rollup[rollup["brand_key"] == brand["key"]]
        if row.empty:
            continue
        with col:
            ui.brand_card(
                df_brand=df[df["brand_key"] == brand["key"]],
                rollup_row=row.iloc[0],
                objects=OBJECTS,
                logo=logo_src(brand["key"], brand.get("logo")),
            )

    ui.section("COMPLETION BY BRAND")
    ui.comparison_panel(rollup)
    ui.legend()
    ui.foot_note(
        "A blank is a record where the property is not set (HubSpot "
        "NOT_HAS_PROPERTY). Archived records are excluded. Completion is field "
        "cells filled divided by field cells possible."
    )

# ---- per brand -------------------------------------------------------------

for tab, brand in zip(tabs[1:], active_brands):
    with tab:
        sub = df[df["brand_key"] == brand["key"]]
        row = rollup[rollup["brand_key"] == brand["key"]]
        if sub.empty or row.empty:
            st.info("No data for this brand. Check its brand values in the sidebar.")
            continue
        r = row.iloc[0]

        ui.brand_banner(brand["name"], logo_src(brand["key"], brand.get("logo")))
        ui.kpi_grid(
            {
                "records": int(r["records"]),
                "blanks": int(r["blanks"]),
                "filled": int(r["filled"]),
                "completion": float(r["completion"]),
            },
            scope=brand["name"].title(),
        )

        for obj in OBJECTS:
            obj_df = sub[sub["object"] == obj]
            if obj_df.empty:
                continue
            ui.section(OBJECT_LABELS.get(obj, obj.upper()))
            show = obj_df[["field", "property", "total", "blanks", "filled", "completion"]].copy()
            show.columns = ["Field", "HubSpot property", "Total", "Blanks", "Filled", "Completion %"]
            st.dataframe(
                show,
                width="stretch",
                hide_index=True,
                column_config={
                    "Completion %": st.column_config.ProgressColumn(
                        "Completion %", min_value=0, max_value=100, format="%.0f%%"
                    ),
                    "Total": st.column_config.NumberColumn(format="%d"),
                    "Blanks": st.column_config.NumberColumn(format="%d"),
                    "Filled": st.column_config.NumberColumn(format="%d"),
                },
            )

        ui.section("WORST FIELDS FIRST")
        worst = sub.sort_values("completion").head(6)
        for _, w in worst.iterrows():
            st.markdown(
                f"**{w['field']}** ({OBJECT_LABELS.get(w['object'], w['object'])}) "
                f"· {int(w['blanks']):,} blank of {int(w['total']):,} "
                f"· {w['completion']:.0f}% complete"
            )

# ---- export ----------------------------------------------------------------

st.download_button(
    "Download summary CSV",
    data=df.to_csv(index=False).encode(),
    file_name=f"hubspot_data_quality_{datetime.now():%Y%m%d}.csv",
    mime="text/csv",
)
