"""
Logo loading.

A brand logo can come from three places, checked in this order:

  1. An explicit "logo" value on the brand in config.py. If it starts with
     http it is used as-is, otherwise it is treated as a path.
  2. A file in assets/ named after the brand key: assets/tcs.svg, assets/bw.png
     and so on.
  3. Nothing, in which case the card falls back to the coloured status dot.

Local files are inlined as base64 data URIs rather than served as static files.
That matters on Streamlit Cloud, where there is no reliable static asset route
and an <img src="assets/tcs.svg"> would simply 404.
"""

from __future__ import annotations

import base64
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# Checked in order. First hit wins, so tcs.svg beats tcs.png.
EXTENSIONS = [".svg", ".png", ".webp", ".jpg", ".jpeg"]

MIME = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _data_uri(path: Path) -> str:
    mime = MIME.get(path.suffix.lower(), "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def find_asset(stem: str) -> Path | None:
    """First file in assets/ matching <stem> with a supported extension."""
    for ext in EXTENSIONS:
        candidate = ASSETS_DIR / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def logo_src(stem: str, explicit: str | None = None) -> str | None:
    """
    Something safe to drop straight into an <img src="...">, or None.

    stem is normally the brand key ("tcs"). Use "logo" for the dashboard-wide
    mark in the page header.
    """
    if explicit == "":
        # Explicitly switched off. Distinct from None, which means auto-discover.
        return None

    if explicit:
        if explicit.startswith(("http://", "https://", "data:")):
            return explicit
        path = Path(explicit)
        if not path.is_absolute():
            path = ASSETS_DIR.parent / path
        if path.is_file():
            return _data_uri(path)
        return None

    found = find_asset(stem)
    return _data_uri(found) if found else None


def logo_path(stem: str = "logo") -> Path | None:
    """
    Real filesystem path, for the Streamlit APIs that want one rather than a
    data URI (st.logo, st.image).
    """
    return find_asset(stem)
