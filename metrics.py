"""
Turns config plus a live property list into a set of HubSpot count queries,
runs them, and hands back tidy DataFrames.

Three ideas do all the work.

Property resolution
    Config gives a human label ("Industry Segment", "Drupal Partners (CMS)")
    and sometimes an internal name. HubSpot only accepts internal names, and a
    search against a property that does not exist returns a 400. So before any
    counting we reconcile every field and every brand marker against the real
    property list. Matching is on the internal name first, then the EXACT
    normalised label. Never a substring: substring matching is what previously
    made "Webinar - TCS/DrupalPartners" shadow "Drupal Partners (CMS)".

Brand membership by marker
    There is no "brand" field. A contact is TCS because its e-Commerce
    Technologies column is filled, BinaryWorks because Drupal Partners (CMS) is
    filled, ConversionBox because ConversionBox Competitors is filled. In HubSpot
    that is the HAS_PROPERTY operator. Because these are independent columns, the
    brands overlap, and a contact can legitimately be counted in two of them.

Blank counting
    A blank is a record where a tracked property is not set, which is
    NOT_HAS_PROPERTY. One search, limit=1, read the total. Nothing is paginated.
"""

from __future__ import annotations

import re
from itertools import combinations, product
from typing import Callable

import pandas as pd

# HubSpot allows a maximum of 5 filterGroups per search.
MAX_FILTER_GROUPS = 5


# ---------------------------------------------------------------------------
# Property resolution
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, strip everything that is not a letter or digit."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def build_label_index(properties: list[dict]) -> dict[str, str]:
    """
    Map normalised label -> internal name. Exact matches only.

    Custom fields win ties against hs_ prefixed internal ones.
    """
    index: dict[str, str] = {}
    for prop in properties:
        key = _normalise(prop["label"])
        if not key:
            continue
        name = prop["name"]
        existing = index.get(key)
        if existing is None:
            index[key] = name
        elif existing.startswith("hs_") and not name.startswith("hs_"):
            index[key] = name
    return index


def _resolve_one(
    wanted: str | None,
    name_set: set[str],
    label_index: dict[str, str],
) -> str | None:
    if not wanted:
        return None
    if wanted in name_set:           # already an internal name
        return wanted
    return label_index.get(_normalise(wanted))   # exact label match, no substrings


def resolve_fields(
    tracked_fields: list[dict],
    properties_by_object: dict[str, list[dict]],
    objects: list[str],
) -> tuple[dict[str, dict[str, str | None]], list[str]]:
    """Returns ({field_label: {object: internal_name_or_None}}, warnings)."""
    name_sets = {o: {p["name"] for p in properties_by_object.get(o, [])} for o in objects}
    label_indexes = {o: build_label_index(properties_by_object.get(o, [])) for o in objects}

    mapping: dict[str, dict[str, str | None]] = {}
    warnings: list[str] = []

    for spec in tracked_fields:
        label = spec["label"]
        mapping[label] = {}
        for obj in objects:
            configured = spec.get(obj)
            hit = _resolve_one(configured, name_sets[obj], label_indexes[obj])
            if hit is None:
                hit = _resolve_one(label, name_sets[obj], label_indexes[obj])
            mapping[label][obj] = hit
            if hit is None and configured:
                warnings.append(
                    f"'{label}': no property named '{configured}' and none labelled "
                    f"'{label}' on {obj}. Skipped."
                )
            elif hit and configured and hit != configured:
                warnings.append(
                    f"'{label}': '{configured}' does not exist, using '{hit}' "
                    f"(matched on label)."
                )

    unresolved = [lab for lab, per in mapping.items() if not any(per.values())]
    if unresolved:
        warnings.append(
            "Not found at all: " + ", ".join(unresolved)
            + ". Open Field mapping in the sidebar and pick them by hand."
        )
    return mapping, warnings


def resolve_markers(
    brands: list[dict],
    properties: list[dict],
) -> tuple[dict[str, str | None], list[str]]:
    """
    Returns ({brand_key: marker_internal_name_or_None}, warnings).

    The marker is the column whose mere presence makes a contact part of the
    brand. Resolved the same careful way as the tracked fields.
    """
    name_set = {p["name"] for p in properties}
    label_index = build_label_index(properties)

    resolved: dict[str, str | None] = {}
    warnings: list[str] = []

    for brand in brands:
        wanted = brand.get("marker")
        hit = _resolve_one(wanted, name_set, label_index)
        resolved[brand["key"]] = hit
        if wanted and hit is None:
            warnings.append(
                f"{brand['name']}: no property named or labelled '{wanted}'. "
                f"This brand cannot be identified. Pick its marker column in "
                f"Brand setup."
            )
    return resolved, warnings


# ---------------------------------------------------------------------------
# Filter construction
# ---------------------------------------------------------------------------

def brand_conditions(brand: dict, marker: str | None) -> list[dict]:
    """
    The OR-ed list of conditions that make a contact part of this brand.

    Normally exactly one: the marker column is filled. extra_rules append more.
    """
    conditions: list[dict] = []
    if marker:
        conditions.append({"propertyName": marker, "operator": "HAS_PROPERTY"})
    for rule in brand.get("extra_rules") or []:
        f = {"propertyName": rule["property"], "operator": rule.get("operator", "EQ")}
        if "value" in rule:
            f["value"] = str(rule["value"])
        conditions.append(f)
    return conditions


def build_filter_groups(
    conditions: list[dict],
    blank_property: str | None = None,
) -> list[dict]:
    """
    HubSpot filterGroups are OR-ed. Filters inside a group are AND-ed.

    One group per brand condition, each carrying the blank filter, which gives
    (cond1 AND blank) OR (cond2 AND blank).
    """
    base = (
        [{"propertyName": blank_property, "operator": "NOT_HAS_PROPERTY"}]
        if blank_property
        else []
    )
    if not conditions:
        return [{"filters": base}] if base else []
    return [{"filters": base + [c]} for c in conditions[:MAX_FILTER_GROUPS]]


def intersection_groups(condition_lists: list[list[dict]]) -> list[dict] | None:
    """
    Filters for "belongs to ALL of these brands at once".

    Each brand is an OR of conditions, and we need the AND of those ORs. HubSpot
    can only express OR-of-ANDs, so we distribute into a cartesian product. With
    one condition per brand the three-way intersection is a single group holding
    three HAS_PROPERTY filters. Add extra_rules and the product grows: two rules
    per brand makes the three-way 2*2*2 = 8 groups, over HubSpot's limit of 5.

    Returns None when it will not fit, so the caller can say so honestly instead
    of printing a number that is quietly wrong.
    """
    if not condition_lists or any(not c for c in condition_lists):
        return None
    combos = list(product(*condition_lists))
    if len(combos) > MAX_FILTER_GROUPS:
        return None
    return [{"filters": list(combo)} for combo in combos]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def plan_queries(
    brands: list[dict],
    objects: list[str],
    field_mapping: dict[str, dict[str, str | None]],
    with_overlap: bool = False,
) -> list[tuple]:
    """Flat list of every API call, so the progress bar can be honest."""
    tasks: list[tuple] = []
    for brand in brands:
        for obj in objects:
            tasks.append(("total", brand, obj, None, None))
            for label, per_obj in field_mapping.items():
                prop = per_obj.get(obj)
                if prop:
                    tasks.append(("blank", brand, obj, label, prop))
    if with_overlap and len(brands) > 1:
        keys = [b["key"] for b in brands]
        for size in range(2, len(keys) + 1):
            for combo in combinations(keys, size):
                tasks.append(("overlap", combo, objects[0], None, None))
    return tasks


def collect_counts(
    clients: dict,
    brands: list[dict],
    objects: list[str],
    field_mapping: dict[str, dict[str, str | None]],
    markers: dict[str, str | None],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> pd.DataFrame:
    """One row per (brand, object, field)."""
    tasks = [t for t in plan_queries(brands, objects, field_mapping) if t[0] != "overlap"]
    total_tasks = len(tasks)

    conditions = {b["key"]: brand_conditions(b, markers.get(b["key"])) for b in brands}

    record_totals: dict[tuple[str, str], int] = {}
    blank_counts: dict[tuple[str, str, str], int] = {}

    for i, (kind, brand, obj, label, prop) in enumerate(tasks, start=1):
        client = clients[brand["key"]]
        groups = build_filter_groups(
            conditions[brand["key"]],
            blank_property=prop if kind == "blank" else None,
        )
        value = client.count(obj, groups)

        if kind == "total":
            record_totals[(brand["key"], obj)] = value
            note = f"{brand['name']}: total records"
        else:
            blank_counts[(brand["key"], obj, label)] = value
            note = f"{brand['name']}: {label}"

        if progress_cb:
            progress_cb(i, total_tasks, note)

    rows = []
    for brand in brands:
        for obj in objects:
            total = record_totals.get((brand["key"], obj), 0)
            for label, per_obj in field_mapping.items():
                prop = per_obj.get(obj)
                if not prop:
                    continue
                blanks = blank_counts.get((brand["key"], obj, label), 0)
                filled = max(total - blanks, 0)
                rows.append(
                    {
                        "brand_key": brand["key"],
                        "brand_name": brand["name"],
                        "marker": markers.get(brand["key"]) or "",
                        "object": obj,
                        "field": label,
                        "property": prop,
                        "total": total,
                        "blanks": blanks,
                        "filled": filled,
                        "completion": round(filled / total * 100, 1) if total else 0.0,
                    }
                )

    df = pd.DataFrame(rows)
    if not df.empty:
        order = {label: i for i, label in enumerate(field_mapping)}
        df["_o"] = df["field"].map(order)
        df = df.sort_values(["brand_key", "object", "_o"]).drop(columns="_o")
    return df.reset_index(drop=True)


def collect_overlaps(
    client,
    object_type: str,
    brands: list[dict],
    markers: dict[str, str | None],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> tuple[dict[frozenset, int], bool]:
    """
    Count the contacts sitting in more than one brand at once.

    Returns ({frozenset_of_brand_keys: count}, expressible). Only combinations
    of two or more are queried; the singletons already come from collect_counts.
    expressible is False when extra_rules made an intersection too complex for
    HubSpot's 5 filter group limit.
    """
    conditions = {b["key"]: brand_conditions(b, markers.get(b["key"])) for b in brands}
    keys = [b["key"] for b in brands]
    names = {b["key"]: b["name"] for b in brands}

    combos = [
        c for size in range(2, len(keys) + 1) for c in combinations(keys, size)
    ]
    out: dict[frozenset, int] = {}
    expressible = True

    for i, combo in enumerate(combos, start=1):
        groups = intersection_groups([conditions[k] for k in combo])
        if groups is None:
            expressible = False
            continue
        out[frozenset(combo)] = client.count(object_type, groups)
        if progress_cb:
            progress_cb(i, len(combos), "overlap: " + " + ".join(names[k] for k in combo))

    return out, expressible


# ---------------------------------------------------------------------------
# Rollups
# ---------------------------------------------------------------------------

def record_totals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["brand_key", "brand_name", "object", "total"])
    return df.groupby(["brand_key", "brand_name", "object"], as_index=False)["total"].max()


def brand_rollup(df: pd.DataFrame) -> pd.DataFrame:
    """Per brand: records, field cells, blanks, completion."""
    if df.empty:
        return pd.DataFrame(
            columns=["brand_key", "brand_name", "marker", "records", "cells",
                     "blanks", "filled", "completion"]
        )
    cells = df.groupby(["brand_key", "brand_name", "marker"], as_index=False).agg(
        cells=("total", "sum"), blanks=("blanks", "sum")
    )
    recs = (
        record_totals(df)
        .groupby(["brand_key", "brand_name"], as_index=False)["total"]
        .sum()
        .rename(columns={"total": "records"})
    )
    out = cells.merge(recs, on=["brand_key", "brand_name"], how="left")
    out["records"] = out["records"].fillna(0).astype(int)
    out["filled"] = out["cells"] - out["blanks"]
    out["completion"] = [
        round(f / c * 100, 1) if c else 0.0 for f, c in zip(out["filled"], out["cells"])
    ]
    return out[["brand_key", "brand_name", "marker", "records", "cells",
                "blanks", "filled", "completion"]]


def exclusive_regions(
    brand_totals: dict[str, int],
    intersections: dict[frozenset, int],
) -> dict[frozenset, int]:
    """
    Size of each region of the Venn diagram, by Mobius inversion.

    exclusive(S) = sum over every superset T of S of (-1)^(|T|-|S|) * |intersect(T)|

    For three brands that gives, for example:
        TCS only    = |TCS| - |TCS n BW| - |TCS n CB| + |TCS n BW n CB|
        TCS n BW only = |TCS n BW| - |TCS n BW n CB|
    """
    keys = list(brand_totals)
    sizes: dict[frozenset, int] = {frozenset([k]): v for k, v in brand_totals.items()}
    sizes.update(intersections)

    regions: dict[frozenset, int] = {}
    for r in range(1, len(keys) + 1):
        for subset in combinations(keys, r):
            s = frozenset(subset)
            acc = 0
            for r2 in range(r, len(keys) + 1):
                for superset in combinations(keys, r2):
                    t = frozenset(superset)
                    if s <= t:
                        acc += (-1) ** (len(t) - len(s)) * sizes.get(t, 0)
            regions[s] = max(acc, 0)   # clamp: rounding cannot make a region negative
    return regions


def overlap_summary(
    rollup: pd.DataFrame,
    intersections: dict[frozenset, int],
) -> dict:
    """
    Everything the overlap panel needs.

    unique     : contacts counted once, however many brands they sit in
    summed     : what you get by adding the brand tabs, which double counts
    duplicated : summed minus unique, the contacts appearing in 2+ brands
    """
    brand_totals = dict(zip(rollup["brand_key"], rollup["records"].astype(int)))
    regions = exclusive_regions(brand_totals, intersections)
    summed = int(sum(brand_totals.values()))
    unique = int(sum(regions.values()))
    multi = int(sum(n for s, n in regions.items() if len(s) > 1))
    return {
        "regions": regions,
        "intersections": intersections,
        "brand_totals": brand_totals,
        "summed": summed,
        "unique": unique,
        "duplicated": max(summed - unique, 0),
        "in_multiple": multi,
    }


def portfolio_kpis(df: pd.DataFrame, overlap: dict | None = None) -> dict:
    """
    The four cards at the top.

    "records" is the UNIQUE contact count when overlap data is available. Adding
    the three brand totals would double count anyone with two markers filled.
    """
    roll = brand_rollup(df)
    if roll.empty:
        return {"records": 0, "blanks": 0, "filled": 0, "completion": 0.0,
                "brands": 0, "duplicated": 0}
    cells = int(roll["cells"].sum())
    blanks = int(roll["blanks"].sum())
    filled = cells - blanks
    records = int(roll["records"].sum())
    duplicated = 0
    if overlap:
        records = overlap["unique"]
        duplicated = overlap["duplicated"]
    return {
        "records": records,
        "blanks": blanks,
        "filled": filled,
        "completion": round(filled / cells * 100, 1) if cells else 0.0,
        "brands": int(roll.shape[0]),
        "duplicated": duplicated,
    }
