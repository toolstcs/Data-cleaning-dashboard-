# HubSpot Data Quality Dashboard

Multi-brand CRM field completeness tracker. For each of ten tracked fields, on
each of three brands, it reports **total records** and **blank count**, and
bands the result green, amber or red.

**Contacts only.** Companies are not read.

Open `preview.html` in a browser to see the layout without setting anything up.

---

## The trick that makes this fast

It never downloads a single record.

HubSpot's CRM Search API returns an accurate `total` on every response, even
when you ask for `limit: 1`. So a blank count for a field is one API call:

```json
POST /crm/v3/objects/contacts/search
{
  "limit": 1,
  "filterGroups": [{
    "filters": [
      { "propertyName": "brand",    "operator": "EQ", "value": "TheCommerceShop" },
      { "propertyName": "jobtitle", "operator": "NOT_HAS_PROPERTY" }
    ]
  }]
}
```

Read `total`, throw the rest away. A portal with 300,000 contacts costs exactly
the same as one with 300.

A full refresh is **33 calls**, 3 brands times 1 record count plus 10 fields.
About 11 seconds, then it caches for 30 minutes.

---

## 1. Get a HubSpot token

HubSpot retired legacy API keys in 2022. You need a **private app access
token**.

1. HubSpot, gear icon, **Settings**
2. **Integrations**, **Private Apps**, **Create a private app**
3. Open the **Scopes** tab and tick:
   - `crm.objects.contacts.read`
   - `crm.schemas.contacts.read`
4. **Create app**, then copy the token. It starts with `pat-na1-`.

Read only. This app never writes to your CRM.

---

## 2. Run it locally

```bash
git clone https://github.com/<you>/hubspot-dq-dashboard.git
cd hubspot-dq-dashboard

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# paste your token into .streamlit/secrets.toml

streamlit run app.py
```

`secrets.toml` is gitignored. It must never reach GitHub.

---

## 3. Brand logos

Drop the real logo files into `assets/`, named after the brand `key` in
`config.py`:

| Brand | key | filename |
|---|---|---|
| The Commerce Shop | `tcs` | `assets/tcs.svg` |
| BinaryWorks | `bw` | `assets/bw.svg` |
| ConversionBox | `cb` | `assets/cb.svg` |

`.svg` is preferred, then `.png`, `.webp`, `.jpg`. The app checks in that order
and stops at the first hit. Files are read from disk and inlined as base64 data
URIs, so they render on Streamlit Cloud with no hosting and no extra request.

An optional dashboard-wide mark goes in `assets/logo.svg`. It appears in the
page header and the top left of the sidebar.

Logos render at 26px tall, capped at 110px wide, `object-fit: contain`. Square
marks and wide wordmarks both work. Transparent backgrounds look best against
the dark panel (`#0d1526`).

Already hosted somewhere? Skip the files and set a URL in `config.py`:

```python
{"key": "tcs", "name": "THE COMMERCE SHOP", "values": ["TheCommerceShop"],
 "logo": "https://thecommerceshop.com/logo.svg"},
```

Set `"logo": ""` to switch it off. No logo means the card falls back to the
coloured status dot on its own. Nothing breaks.

**The three SVGs in `assets/` right now are placeholders.** Replace them.

---

## 4. Point it at your data

The first run will not know your portal. Two sidebar panels fix that in about
two minutes, and neither needs a code change.

### Brand setup

Tells the app how HubSpot marks a contact as TCS, BinaryWorks or ConversionBox.
Three modes:

| Mode | Use when |
|---|---|
| **One portal, brand property** | All three brands live in one portal and a property (`brand`, `business_unit`, `hs_all_assigned_business_unit_ids`) says which. |
| **Three portals, three tokens** | Each brand is a separate HubSpot account. Add the three tokens under `[hubspot.tokens]` in secrets. |
| **No split** | Everything in one bucket. Good for a first smoke test. |

In property mode the panel lists every candidate property in your portal, with
brand-looking ones sorted first, and shows the real dropdown values so you can
tick which value belongs to which brand. It then prints a `config.py` snippet.
Paste that in and the setup is permanent.

### Field mapping

These are the ten tracked fields:

| Field | Contacts property |
|---|---|
| Job Title | `jobtitle` |
| Website URL | `website` |
| Company Name | `company` |
| Industry Segment | custom |
| Priority Contacts | custom |
| Revenue Range | custom |
| Industry | `industry` |
| Annual Revenue | `annualrevenue` |
| Custom Timezone | custom |
| Company Size | custom |

Six of the ten are custom fields, so their internal names are specific to your
portal.

HubSpot only accepts internal names, and a search against a property that does
not exist returns a 400. So on startup the app pulls your real property list and
reconciles every field against it: it trusts the configured internal name if it
exists, and otherwise matches on the label. That is how a custom field called
"Industry Segment" gets found even when its internal name is
`industry_segment_2`.

Anything it still cannot find is marked **n/a** and dropped from the maths. It
is never counted as 100% blank, because a field that does not exist is not the
same thing as a field nobody filled in.

Override any mapping in the **Field mapping** panel, then paste the internal
names into `TRACKED_FIELDS` in `config.py` to lock them in.

Prefer a spreadsheet? Dump every property instead:

```bash
export HUBSPOT_TOKEN=pat-na1-xxxxxxxx
python discover_properties.py
# writes properties_contacts.csv, and flags anything that looks like a brand field
```

---

## 5. Push to GitHub

```bash
git init
git add .
git commit -m "HubSpot data quality dashboard"
git branch -M main
git remote add origin https://github.com/<you>/hubspot-dq-dashboard.git
git push -u origin main
```

Run `git status` before the first commit and confirm `.streamlit/secrets.toml`
is **not** listed. If it is, the `.gitignore` did not take.

---

## 6. Deploy to Streamlit Community Cloud

1. [share.streamlit.io](https://share.streamlit.io), **New app**
2. Pick the repo, branch `main`, main file `app.py`
3. **Advanced settings**, **Secrets**, paste:

```toml
[hubspot]
token = "pat-na1-xxxxxxxx"
```

4. **Deploy**

Do not upload `secrets.toml`. Streamlit Cloud injects the secrets box contents
as `st.secrets` at runtime.

The app is public unless the repo is private and you restrict viewers under
Settings, Sharing. A HubSpot token in a public app is a real risk, so lock
viewers down.

---

## Reading the dashboard

- **Green**, 90% or more complete
- **Amber**, 70% to 89%
- **Red**, under 70%, priority cleanup

The 70 and 90 marks appear as ticks on the comparison bars so you can see how
far off a brand is at a glance. Change them in `config.py` (`GREEN_AT`,
`AMBER_AT`).

**Completion** is field cells filled divided by field cells possible. One cell
is one field on one record, so 5,000 contacts times 10 fields is 50,000 cells.

Click a brand name in the tab bar for that brand on its own: its own KPI row, a
sortable table, and a worst-fields-first list.

---

## Things worth knowing

- **A blank means the property is not set** (`NOT_HAS_PROPERTY`). A property set
  to an empty string is treated the same way by HubSpot search.
- **Archived contacts are excluded.** HubSpot search only returns live records.
- **Rate limits.** The CRM Search API is capped at 5 requests per second at the
  account level, shared across every search endpoint and every integration on
  the portal. The app throttles to 3 per second by default and honours a 429
  with backoff. Raise it in the Performance panel only if nothing else is
  hitting the portal.
- **Cache.** Counts are held for 30 minutes per session. Use **Refresh from
  HubSpot** to force a refetch.
- **Brand values cap at 5 per brand,** because HubSpot allows a maximum of 5
  filter groups per search.
- **Bringing companies back** is one line: add `"companies"` to `OBJECTS` in
  `config.py` and give each field a `"companies"` key. The resolver, the cards,
  the tabs and the maths are all driven by that list, so nothing else changes.
  Add the two company scopes to the private app as well.

---

## Files

```
app.py                  Streamlit app: sidebar, tabs, render
config.py               Brands, fields, logos, thresholds. Edit this one.
hubspot_client.py       API client: rate limiting, retries, count-only search
metrics.py              Field resolution, filter building, counting, rollups
ui.py                   CSS and the HTML card renderers
assets_loader.py        Logo lookup and base64 inlining
assets/                 Brand logos. Replace the placeholders.
discover_properties.py  Optional: dump every property to CSV
preview.html            Static preview, synthetic numbers
tests/                  Offline tests, no token required
```

Run the tests any time without a token:

```bash
python tests/test_offline.py     # resolver, filters, logo loader, maths
python tests/test_app_smoke.py   # boots the real app against a stubbed HubSpot
python tests/make_preview.py     # regenerate preview.html
```
