"""
Central configuration for the HubSpot Data Quality Dashboard.

Almost everything you will ever need to change lives in this one file.
"""

# ---------------------------------------------------------------------------
# App chrome
# ---------------------------------------------------------------------------

APP_TITLE = "HUBSPOT DATA QUALITY DASHBOARD"
APP_SUBTITLE = "CRM field completeness tracker, multi-brand view"

# "light" (white background) or "dark" (the original void background).
# If you flip this, also flip base in .streamlit/config.toml so Streamlit's own
# chrome (sidebar, widgets, tooltips) matches. Those two cannot read each other.
THEME = "light"

# Optional dashboard-wide logo, shown in the page header and the sidebar.
# None means: look for assets/logo.svg (or .png, .webp, .jpg). Set a URL or a
# path here to override. Set to "" to switch it off entirely.
HEADER_LOGO = None

# Objects the completeness check runs against.
#
# Contacts only. To bring companies back, add "companies" to this list and give
# each field in TRACKED_FIELDS a "companies" key. Nothing else needs to change:
# the resolver, the cards, the tabs and the maths are all driven by this list.
OBJECTS = ["contacts"]

OBJECT_LABELS = {
    "contacts": "CONTACTS",
    "companies": "COMPANIES",
}


# ---------------------------------------------------------------------------
# 1. BRANDS
# ---------------------------------------------------------------------------
# BRAND_MODE decides how a record gets assigned to a brand.
#
#   "property" : one HubSpot portal, one token. A property on the record
#                (for example "brand" or "business_unit" or
#                "hs_all_assigned_business_unit_ids") holds the brand.
#                Set BRAND_PROPERTY below and give each brand its "values".
#
#   "portal"   : three separate HubSpot portals, one private app token each.
#                Put the three tokens in secrets.toml under [hubspot.tokens].
#                BRAND_PROPERTY and "values" are ignored in this mode.
#
#   "single"   : no brand split, everything rolls into one bucket. Good for a
#                first smoke test before the brand field is wired up.
#
# If you are not sure which one you need, leave it on "property", start the
# app, and open the "Brand setup" panel in the sidebar. It lists every
# candidate property in your portal with its real values, and prints a config
# snippet you can paste straight back in here.

BRAND_MODE = "property"

# Internal property name (not the label) that holds the brand.
BRAND_PROPERTY = {
    "contacts": "brand",
}

# "values" is the list of raw property values that map to each brand.
# A record matches the brand if the brand property equals ANY value in the list.
# Maximum of 5 values per brand (HubSpot caps a search at 5 filter groups).
#
# "logo" is optional:
#   None  -> look for assets/<key>.svg, then .png, .webp, .jpg
#   "..." -> a URL, or a path relative to the project root
#   ""    -> no logo, fall back to the coloured status dot
BRANDS = [
    {"key": "tcs", "name": "THE COMMERCE SHOP", "values": ["TheCommerceShop"], "logo": None},
    {"key": "bw",  "name": "BINARYWORKS",       "values": ["BinaryWorks"],     "logo": None},
    {"key": "cb",  "name": "CONVERSIONBOX",     "values": ["ConversionBox"],   "logo": None},
]


# ---------------------------------------------------------------------------
# 2. TRACKED FIELDS
# ---------------------------------------------------------------------------
# One entry per field you want a total count and a blank count for.
#
#   label     : what shows on the dashboard.
#   contacts  : internal property name on the contact object, or None.
#
# A None (or a name that does not exist in your portal) is not fatal. On
# startup the app pulls your real property list and tries to match the label,
# so a custom field called "Industry Segment" will be found even if its
# internal name is something like "industry_segment_2". Anything it still
# cannot find is shown as "n/a" and left out of the maths, never counted as
# 100% blank.
#
# Six of these ten are custom fields, so their internal names are portal
# specific. Once the app shows you the correct names in the "Field mapping"
# panel, paste them in here to lock them down.

TRACKED_FIELDS = [
    {"label": "Job Title",         "contacts": "jobtitle"},
    {"label": "Website URL",       "contacts": "website"},
    {"label": "Company Name",      "contacts": "company"},
    {"label": "Industry Segment",  "contacts": None},
    {"label": "Priority Contacts", "contacts": None},
    {"label": "Revenue Range",     "contacts": None},
    {"label": "Industry",          "contacts": "industry"},
    {"label": "Annual Revenue",    "contacts": "annualrevenue"},
    {"label": "Custom Timezone",   "contacts": None},
    {"label": "Company Size",      "contacts": None},
]


# ---------------------------------------------------------------------------
# 3. THRESHOLDS AND PERFORMANCE
# ---------------------------------------------------------------------------

GREEN_AT = 90   # completion at or above this is green
AMBER_AT = 70   # completion at or above this is amber, below it is red

# HubSpot caps the CRM Search API at 5 requests per second, shared across the
# whole account and across every search endpoint. 3.0 leaves headroom for any
# other integration hitting the same portal. Raise it only if you know nothing
# else is running.
SEARCH_RATE_PER_SEC = 3.0

# How long a set of counts stays fresh before the app will refetch.
CACHE_TTL_SECONDS = 1800  # 30 minutes

REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
