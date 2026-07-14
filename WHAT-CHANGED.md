# What changed, and what to upload

You do **not** need to delete anything in GitHub first. Uploading a file with
the same path overwrites it. Files you do not upload are left untouched.

## Required (Streamlit will not work without these)

| File | Why |
|---|---|
| `app.py` | Rewritten for marker-based brands and the overlap panel |
| `config.py` | Brands are now marker columns, not a brand property. Adds `THEME` |
| `metrics.py` | `HAS_PROPERTY` filters, exact-label resolution, overlap maths |
| `ui.py` | Light palette, overlap panel, marker tags, banded detail table |
| `.streamlit/config.toml` | Switches Streamlit's own chrome to light. Without it the sidebar stays dark while the page goes white |
| `assets/tcs.svg` | Real Commerce Shop logo |
| `assets/bw.svg` | Real BinaryWorks logo |
| `assets/cb.svg` | Real ConversionBox logo |

## Optional (docs and tests, the app runs fine without them)

| File | Why |
|---|---|
| `README.md` | Setup, the marker rule, the BinaryWorks undercount warning |
| `assets/README.md` | Logo naming and replacement |
| `preview.html` | Static preview with synthetic numbers |
| `tests/test_offline.py` | Resolver, filters, overlap maths |
| `tests/test_app_smoke.py` | Boots the app against a stubbed HubSpot |
| `tests/make_preview.py` | Regenerates `preview.html` |

## Unchanged, leave them alone

```
hubspot_client.py
assets_loader.py
discover_properties.py
requirements.txt
.gitignore
.streamlit/secrets.toml.example
```

## Uploading without deleting

1. Open the repo on GitHub
2. **Add file** -> **Upload files**
3. Drag the `assets` and `.streamlit` **folders** and the loose `.py` files in
   together. Chrome and Edge preserve folder structure on a folder drag.
4. Commit

Same paths get overwritten. Everything else stays.

**Careful:** dragging loose files puts them at the repo root. `tcs.svg` dropped
on its own lands at `/tcs.svg`, not `/assets/tcs.svg`, and the logo will not
load. Drag the folder, not the file inside it.

## The better way, so this stops being a chore

```bash
git pull
# copy the changed files into your local clone, overwriting
git add -A
git commit -m "Marker-based brands, overlap counts, light theme, real logos"
git push
```

Streamlit Cloud redeploys automatically on push. No uploads, no deleting, and
`git diff` shows you exactly what changed before you commit.

If you would rather not use the terminal, GitHub Desktop does the same thing:
drop the files into the local folder, it shows you the diff, click Commit, click
Push.
