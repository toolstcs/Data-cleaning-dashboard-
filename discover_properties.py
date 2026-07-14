"""
One-off helper. Dumps every contact and company property in your HubSpot
portal to CSV so you can read off the real internal names and paste them into
config.py.

Usage:

    export HUBSPOT_TOKEN=pat-na1-xxxxxxxx
    python discover_properties.py

Writes properties_contacts.csv next to the script (one CSV per object in
config.OBJECTS),
and prints a short list of anything that looks like it could be your brand
field.

You do not have to run this. The dashboard resolves properties automatically on
startup and the sidebar lets you fix any mapping by hand. This is just faster if
you would rather sort through 400 properties in a spreadsheet.
"""

from __future__ import annotations

import csv
import os
import sys

from config import OBJECTS
from hubspot_client import HubSpotClient, HubSpotError

BRAND_HINTS = (
    "brand",
    "business unit",
    "business_unit",
    "division",
    "portal",
    "company brand",
)


def main() -> int:
    token = os.environ.get("HUBSPOT_TOKEN", "").strip()
    if not token:
        print("Set HUBSPOT_TOKEN first, for example:")
        print("  export HUBSPOT_TOKEN=pat-na1-xxxxxxxx")
        return 1

    client = HubSpotClient(token)

    for obj in OBJECTS:
        try:
            props = client.list_properties(obj)
        except HubSpotError as exc:
            print(f"Failed on {obj}: {exc}")
            return 1

        path = f"properties_{obj}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["internal_name", "label", "type", "fieldType", "group", "options"])
            for p in sorted(props, key=lambda x: x["label"].lower()):
                writer.writerow(
                    [
                        p["name"],
                        p["label"],
                        p["type"],
                        p["fieldType"],
                        p["group"],
                        " | ".join(str(o) for o in p["options"]),
                    ]
                )
        print(f"{len(props):>4} properties on {obj:<10} -> {path}")

        candidates = [
            p
            for p in props
            if any(h in f"{p['name']} {p['label']}".lower() for h in BRAND_HINTS)
        ]
        if candidates:
            print(f"     possible brand fields on {obj}:")
            for c in candidates:
                opts = ", ".join(str(o) for o in c["options"][:8]) or "(free text)"
                print(f"       {c['name']:<40} {c['label']:<32} values: {opts}")
        print()

    print("Paste the internal names you want into TRACKED_FIELDS in config.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
