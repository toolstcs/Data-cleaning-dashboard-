"""
HubSpot Data Quality Dashboard.

Same shape as the old Lead Database Dashboard: brand pill toggle, stat cards,
horizontal bar rows. The bars used to measure leads per technology. They now
measure BLANKS per tracked field.

Counts only. For every tracked field, on every brand, the app asks HubSpot two
questions: how many contacts are in this brand, and how many have this property
unset. Both answers come back as the "total" on a search response, so a portal
with 450,000 contacts costs the same as one with 450.

Brands are not a field. A contact is TCS because e_commerce_technologies is
filled, BinaryWorks because drupal_partners__cms_ is filled, ConversionBox
because conversionbox_competitors is filled. Independent columns, so a contact
can sit in two brands. The overlap panel counts how many do.

Run locally:   streamlit run app.py
"""

from __future__ import annotations

import hashlib
import json
import time

import streamlit as st

from config import (
    BRAND_MODE,
    BRANDS,
    CACHE_TTL_SECONDS,
    MAX_RETRIES,
    OBJECTS,
    REQUEST_TIMEOUT,
    SEARCH_RATE_PER_SEC,
    SHOW_OVERLAP,
    TRACKED_FIELDS,
)
from dashboard_html import build_page, build_payload
from hubspot_client import HubSpotClient, HubSpotError
from metrics import (
    brand_rollup,
    collect_counts,
    collect_overlaps,
    overlap_summary,
    plan_queries,
    resolve_fields,
    resolve_markers,
)

st.set_page_config(
    page_title="HubSpot Data Quality",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# The dashboard itself lives in an iframe with its own stylesheet, so Streamlit's
# theme cannot reach it. All this page needs is to get out of the way.
st.markdown(
    "<style>#MainMenu,header,footer{visibility:hidden}"
    ".block-container{padding:0!important;max-width:100%!important}"
    "iframe{border:none!important}</style>",
    unsafe_allow_html=True,
)

MODES = ["marker", "portal", "single"]
MODE_LABELS = {
    "marker": "Marker column per brand",
    "portal": "Three portals, three tokens",
    "single": "No split (one bucket)",
}


# ---------------------------------------------------------------------------
# Secrets and schema
# ---------------------------------------------------------------------------

def load_tokens() -> dict[str, str]:
    try:
        hs = st.secrets["hubspot"]
    except Exception:
        st.error("No HubSpot credentials found.")
        st.markdown(
            "Paste this into **Manage app, Settings, Secrets** on Streamlit Cloud, "
            "or into `.streamlit/secrets.toml` locally:\n\n"
            "```toml\n[hubspot]\ntoken = \"pat-na1-xxxxxxxx\"\n```\n\n"
            "That is a private app access token, not a legacy API key. Scopes: "
            "`crm.objects.contacts.read` and `crm.schemas.contacts.read`."
        )
        st.stop()

    if st.session_state.get("brand_mode", BRAND_MODE) == "portal":
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
    client = HubSpotClient(token, SEARCH_RATE_PER_SEC, REQUEST_TIMEOUT, MAX_RETRIES)
    return client.list_properties(object_type)


def cache_key(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


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
            "A contact is in a brand when that brand's marker column is not empty. "
            "A presence check, not a value match."
        )
        NO_MARKER = "(no marker, brand disabled)"
        names = sorted(p["name"] for p in CONTACT_PROPS)
        labels = {p["name"]: p["label"] for p in CONTACT_PROPS}

        # Bind the constants as defaults: Streamlit can re-invoke format_func
        # after this block has run, and a plain closure over module scope
        # silently mangles the label once the name is rebound elsewhere.
        def fmt(n, _none=NO_MARKER, _labels=labels):
            return n if n == _none else f"{_labels.get(n, n)}  ({n})"

        for brand in active_brands:
            key = brand["key"]
            options = [NO_MARKER] + names
            current = markers.get(key) or NO_MARKER
            picked = st.selectbox(
                brand["short"],
                options=options,
                index=options.index(current) if current in options else 0,
                format_func=fmt,
                key=f"marker_{key}",
                help=f"config.py asks for: {brand.get('marker')}",
            )
            markers[key] = None if picked == NO_MARKER else picked

        st.code(
            "BRANDS = [\n"
            + "".join(
                f'    {{"key": "{b["key"]}", "marker": {markers[b["key"]]!r}, ...}},\n'
                for b in active_brands
            )
            + "]\n",
            language="python",
        )

elif mode == "single":
    active_brands = [
        {"key": BRANDS[0]["key"], "name": "ALL CONTACTS", "short": "All contacts",
         "marker": None, "extra_rules": [], "logo": "",
         "accent": "#4338ED", "accent2": "#F97316"}
    ]
    markers = {active_brands[0]["key"]: None}
else:
    markers = {b["key"]: None for b in active_brands}

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
                obj,
                options=opts,
                index=opts.index(current) if current in opts else 0,
                key=f"map_{label}_{obj}",
            )
            field_mapping[label][obj] = None if picked == NOT_TRACKED else picked

with st.sidebar.expander("Performance", expanded=False):
    rate = st.slider("Search requests per second", 1.0, 5.0, float(SEARCH_RATE_PER_SEC), 0.5)
    ttl = st.number_input("Cache results for (minutes)", 1, 1440, CACHE_TTL_SECONDS // 60)
    want_overlap = st.checkbox("Count contacts in 2+ brands", value=SHOW_OVERLAP)

refresh = st.sidebar.button("Refresh from HubSpot", width="stretch", type="primary")

for w in field_warnings:
    st.sidebar.warning(w)
for w in marker_warnings:
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

# A brand with no marker sends no filter, so HubSpot returns the whole portal and
# every brand shows the same number. Refuse to fetch rather than show that.
if mode == "marker":
    unmapped = [b["short"] for b in active_brands if not markers.get(b["key"])]
    if unmapped:
        st.error(f"**Brand marker missing:** {', '.join(unmapped)}")
        asked = "\n".join(
            f"- **{b['short']}** wants `{b.get('marker')}`"
            for b in active_brands
            if not markers.get(b["key"])
        )
        st.markdown(
            "A brand is defined by a column being *filled*. With no marker the search "
            "would carry no filter and every brand would count your entire portal, so "
            "the numbers are withheld.\n\n"
            f"{asked}\n\n"
            "Those internal names do not exist in this portal. Open **Brand setup** in "
            "the sidebar and pick the real column."
        )
        st.stop()


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

overlap_on = want_overlap and mode == "marker" and len(active_brands) > 1

payload_key = cache_key(
    {
        "mode": mode,
        "brands": [{"k": b["key"], "x": b.get("extra_rules")} for b in active_brands],
        "markers": markers,
        "fields": tracked_now,
        "objects": OBJECTS,
        "overlap": overlap_on,
    }
)
cached = st.session_state["counts_cache"].get(payload_key)
fresh = cached and (time.time() - cached["ts"] < ttl * 60) and not refresh

if fresh:
    df = cached["df"]
    inters = {frozenset(k): v for k, v in cached["inters"]}
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
        df = collect_counts(clients, active_brands, OBJECTS, tracked_now, markers, tick)
        inters = {}
        if overlap_on:
            inters, _ = collect_overlaps(
                clients[active_brands[0]["key"]], OBJECTS[0], active_brands, markers, tick
            )
    except HubSpotError as exc:
        bar.empty()
        st.error(str(exc))
        st.stop()

    bar.empty()
    fetched_at = time.time()
    st.session_state["counts_cache"][payload_key] = {
        "df": df,
        "inters": [(tuple(sorted(k)), v) for k, v in inters.items()],
        "ts": fetched_at,
    }


# ---------------------------------------------------------------------------
# Post-flight sanity, then render
# ---------------------------------------------------------------------------

rollup = brand_rollup(df)
summary = overlap_summary(rollup, inters) if (overlap_on and inters) else None

if len(active_brands) > 1 and not rollup.empty:
    counts = rollup.set_index("brand_name")["records"]
    if counts.nunique() == 1 and counts.iloc[0] > 0:
        st.error(
            f"**Every brand returned {int(counts.iloc[0]):,} contacts.** Different marker "
            "columns almost never have identical fill counts, so the markers are probably "
            "all pointing at the same property. Check Brand setup."
        )
    zeros = [n for n, v in counts.items() if v == 0]
    if zeros:
        st.warning(
            f"**Zero contacts matched for {', '.join(zeros)}.** Either that marker column "
            "really is empty on every contact, or the wrong column is selected."
        )

page = build_page(build_payload(df, rollup, active_brands, summary, fetched_at))

# st.components.v1.html was retired on 2026-06-01 in favour of st.iframe, which
# also auto-sizes to its content instead of needing a hardcoded pixel height.
# The fallback keeps this working on older Streamlit.
if hasattr(st, "iframe"):
    st.iframe(page, height="content")
else:  # pragma: no cover
    import streamlit.components.v1 as components

    components.html(page, height=1600, scrolling=True)

st.download_button(
    "Download summary CSV",
    data=df.to_csv(index=False).encode(),
    file_name=f"hubspot_data_quality_{time.strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
