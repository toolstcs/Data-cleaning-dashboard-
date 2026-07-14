"""
Turns config plus a live property list into a set of HubSpot count queries,
runs them, and hands back a tidy DataFrame.

Two ideas do all the work here.

Field resolution
    Your config gives a human label ("Industry Segment") and, optionally, an
    internal name. HubSpot only accepts internal names, and a search against a
    property that does not exist returns a 400. So before any counting happens
    we reconcile every field against the real property list pulled from the
    portal. A field that cannot be resolved on an object is marked unavailable
    and dropped from that object's maths, rather than silently reported as
    100% blank.

Blank counting
    A blank is a record where the property is not set, which HubSpot expresses
    as the NOT_HAS_PROPERTY operator. One search, limit=1, read the total.
"""

from __future__ import annotations

import re
from typing import Callable

import pandas as pd


# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, strip everything that is not a letter or digit."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def build_label_index(properties: list[dict]) -> dict[str, str]:
    """
    Map normalised label -> internal name.

    HubSpot ships plenty of near-duplicate labels, and internal properties
    prefixed hs_ often shadow the custom field you actually want. Custom
    fields win ties.
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


def resolve_fields(
    tracked_fields: list[dict],
    properties_by_object: dict[str, list[dict]],
    objects: list[str],
) -> tuple[dict[str, dict[str, str | None]], list[str]]:
    """
    Returns (mapping, warnings).

    mapping is {field_label: {object: internal_name_or_None}}.
    """
    name_sets = {
        obj: {p["name"] for p in properties_by_object.get(obj, [])} for obj in objects
    }
    label_indexes = {
        obj: build_label_index(properties_by_object.get(obj, [])) for obj in objects
    }

    mapping: dict[str, dict[str, str | None]] = {}
    warnings: list[str] = []

    for spec in tracked_fields:
        label = spec["label"]
        mapping[label] = {}
        for obj in objects:
            configured = spec.get(obj)

            # 1. Trust the configured internal name if it genuinely exists.
            if configured and configured in name_sets[obj]:
                mapping[label][obj] = configured
                continue

            # 2. Otherwise fall back to matching on the human label.
            guess = label_indexes[obj].get(_normalise(label))
            if guess:
                mapping[label][obj] = guess
                if configured:
                    warnings.append(
                        f"'{label}' on {obj}: '{configured}' does not exist in this "
                        f"portal, using '{guess}' instead (matched on label)."
                    )
                continue

            # 3. Nothing found. Not fatal, just not tracked on this object.
            mapping[label][obj] = None
            if configured:
                warnings.append(
                    f"'{label}' on {obj}: '{configured}' does not exist and no "
                    f"property carries that label. Skipped."
                )

    unresolved = [
        label
        for label, per_obj in mapping.items()
        if not any(per_obj.get(o) for o in objects)
    ]
    if unresolved:
        warnings.append(
            "Not found on contacts or companies: "
            + ", ".join(unresolved)
            + ". Open Field mapping in the sidebar and pick them by hand."
        )

    return mapping, warnings


# ---------------------------------------------------------------------------
# Filter construction
# ---------------------------------------------------------------------------

def build_filter_groups(
    brand_values: list,
    brand_property: str | None,
    blank_property: str | None = None,
) -> list[dict]:
    """
    HubSpot filterGroups are OR'd, filters inside a group are AND'd.

    One group per brand value, rather than a single IN filter, because HubSpot
    forces IN values to lowercase on string properties and that quietly returns
    zero rows when the stored value is mixed case. EQ has no such trap.
    """
    base: list[dict] = []
    if blank_property:
        base.append({"propertyName": blank_property, "operator": "NOT_HAS_PROPERTY"})

    values = [v for v in (brand_values or []) if str(v).strip() != ""]

    if not brand_property or not values:
        return [{"filters": base}] if base else []

    # HubSpot allows a maximum of 5 filter groups per search.
    return [
        {"filters": base + [{"propertyName": brand_property, "operator": "EQ", "value": str(v)}]}
        for v in values[:5]
    ]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def plan_queries(
    brands: list[dict],
    objects: list[str],
    field_mapping: dict[str, dict[str, str | None]],
) -> list[tuple]:
    """
    Flat list of every API call we are about to make, so the progress bar can
    be honest about how long this will take.

    Each item is (kind, brand, object, field_label, property_name).
    """
    tasks: list[tuple] = []
    for brand in brands:
        for obj in objects:
            tasks.append(("total", brand, obj, None, None))
            for label, per_obj in field_mapping.items():
                prop = per_obj.get(obj)
                if prop:
                    tasks.append(("blank", brand, obj, label, prop))
    return tasks


def collect_counts(
    clients: dict,
    brands: list[dict],
    objects: list[str],
    field_mapping: dict[str, dict[str, str | None]],
    brand_property: dict[str, str | None],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> pd.DataFrame:
    """
    Runs every count and returns one row per (brand, object, field).

    Columns: brand_key, brand_name, object, field, property, total, blanks,
             filled, completion.
    """
    tasks = plan_queries(brands, objects, field_mapping)
    total_tasks = len(tasks)

    record_totals: dict[tuple[str, str], int] = {}
    blank_counts: dict[tuple[str, str, str], int] = {}

    for i, (kind, brand, obj, label, prop) in enumerate(tasks, start=1):
        client = clients[brand["key"]]
        prop_for_brand = brand_property.get(obj)
        groups = build_filter_groups(
            brand_values=brand.get("values", []),
            brand_property=prop_for_brand,
            blank_property=prop if kind == "blank" else None,
        )

        value = client.count(obj, groups)

        if kind == "total":
            record_totals[(brand["key"], obj)] = value
            note = f"{brand['name']} / {obj}: total records"
        else:
            blank_counts[(brand["key"], obj, label)] = value
            note = f"{brand['name']} / {obj}: {label}"

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
                completion = (filled / total * 100.0) if total else 0.0
                rows.append(
                    {
                        "brand_key": brand["key"],
                        "brand_name": brand["name"],
                        "object": obj,
                        "field": label,
                        "property": prop,
                        "total": total,
                        "blanks": blanks,
                        "filled": filled,
                        "completion": round(completion, 1),
                    }
                )

    df = pd.DataFrame(rows)
    if not df.empty:
        order = {spec: i for i, spec in enumerate(field_mapping.keys())}
        df["_o"] = df["field"].map(order)
        df = df.sort_values(["brand_key", "object", "_o"]).drop(columns="_o")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Rollups
# ---------------------------------------------------------------------------

def record_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Distinct record count per brand and object (not per field)."""
    if df.empty:
        return pd.DataFrame(columns=["brand_key", "brand_name", "object", "total"])
    return (
        df.groupby(["brand_key", "brand_name", "object"], as_index=False)["total"]
        .max()
    )


def brand_rollup(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per brand: how many field cells exist, how many are blank, completion %.

    A "cell" is one field on one record. Contacts and companies are added
    together, which is what the brand card headline number reports.
    """
    if df.empty:
        return pd.DataFrame(
            columns=["brand_key", "brand_name", "records", "cells", "blanks", "filled", "completion"]
        )

    cells = df.groupby(["brand_key", "brand_name"], as_index=False).agg(
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
        round(f / c * 100, 1) if c else 0.0
        for f, c in zip(out["filled"], out["cells"])
    ]
    return out[["brand_key", "brand_name", "records", "cells", "blanks", "filled", "completion"]]


def portfolio_kpis(df: pd.DataFrame) -> dict:
    """The four cards at the top of the page."""
    roll = brand_rollup(df)
    if roll.empty:
        return {"records": 0, "blanks": 0, "filled": 0, "completion": 0.0, "brands": 0}
    cells = int(roll["cells"].sum())
    blanks = int(roll["blanks"].sum())
    filled = cells - blanks
    return {
        "records": int(roll["records"].sum()),
        "blanks": blanks,
        "filled": filled,
        "completion": round(filled / cells * 100, 1) if cells else 0.0,
        "brands": int(roll.shape[0]),
    }
