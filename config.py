"""
Central configuration for the HubSpot Data Quality Dashboard.

Almost everything you will ever need to change lives in this one file.
"""

# ---------------------------------------------------------------------------
# App chrome
# ---------------------------------------------------------------------------

APP_TITLE = "HUBSPOT DATA QUALITY DASHBOARD"
APP_SUBTITLE = "CRM field completeness tracker, multi-brand view"

# Optional dashboard-wide logo, shown in the page header and the sidebar.
# None means: look for assets/logo.svg (or .png, .webp, .jpg). Set a URL or a
# path here to override. Set to "" to switch it off entirely.
HEADER_LOGO = None

# Objects the completeness check runs against.
#
# Contacts only. To bring companies back, add "companies" to this list and give
# each field in TRACKED_FIELDS a "companies" key.
OBJECTS = ["contacts"]

OBJECT_LABELS = {
    "contacts": "CONTACTS",
    "companies": "COMPANIES",
}


# ---------------------------------------------------------------------------
# 1. BRANDS
# ---------------------------------------------------------------------------
# BRAND_MODE decides how a contact gets assigned to a brand.
#
#   "marker"  : one portal, one token. A contact belongs to a brand when that
#               brand's MARKER COLUMN is not empty. This is your setup:
#
#                 e-Commerce Technologies filled  -> TCS
#                 Drupal Partners (CMS)   filled  -> BinaryWorks
#                 ConversionBox Competitors filled -> ConversionBox
#
#               Note this is HAS_PROPERTY, not equality. There is no single
#               "brand" field. A contact with two markers filled belongs to
#               two brands, which is why the overlap panel exists.
#
#   "portal"  : three separate HubSpot portals, one private app token each.
#               Put the tokens in secrets.toml under [hubspot.tokens].
#               Markers are ignored.
#
#   "single"  : no brand split, everything in one bucket.

BRAND_MODE = "marker"

# "marker" may be given as the human LABEL or as the internal name. On startup
# the app reconciles it against your live property list, matching the internal
# name first and then the exact normalised label. It never substring-matches,
# which is what previously caused "Webinar - TCS/DrupalPartners" to be picked up
# instead of "Drupal Partners (CMS)".
#
# "extra_rules" is an escape hatch, normally empty. Each entry widens the brand
# to: marker is filled OR <this condition>. See the note below before using it.
# The marker internal names below are lifted verbatim from the old lead
# dashboard's HS_PROPS, so they are known-correct, not guesses. Note the DOUBLE
# underscore in drupal_partners__cms_ ; that is how HubSpot mangled the label
# "Drupal Partners (CMS)".
#
# accent / accent2 drive the per-brand theme, same palette as the old dashboard.
BRANDS = [
    {
        "key": "tcs",
        "name": "THE COMMERCE SHOP",
        "short": "TCS",
        "marker": "e_commerce_technologies",
        "accent": "#4338ED",
        "accent2": "#F97316",
        "extra_rules": [],
        "logo": None,
    },
    {
        "key": "bw",
        "name": "BINARYWORKS",
        "short": "BinaryWorks",
        "marker": "drupal_partners__cms_",
        "accent": "#8B5CF6",
        "accent2": "#F59E0B",
        "extra_rules": [],
        "logo": None,
    },
    {
        "key": "cb",
        "name": "CONVERSIONBOX",
        "short": "ConversionBox",
        "marker": "conversionbox_competitors",
        "accent": "#2563EB",
        "accent2": "#10B981",
        "extra_rules": [],
        "logo": None,
    },
]

# ---------------------------------------------------------------------------
# On extra_rules, and the BinaryWorks undercount
# ---------------------------------------------------------------------------
# In the earlier lead dashboard build, only about 1,400 contacts had
# "Drupal Partners (CMS)" filled, while roughly 138,000 carried TAG = Drupal.
# Marker-only detection therefore undercounted BinaryWorks by two orders of
# magnitude, and the fix was to widen the rule to "marker filled OR TAG matches".
#
# If BinaryWorks comes back looking far too small, that is why. Widen it:
#
#   {
#       "key": "bw",
#       "name": "BINARYWORKS",
#       "marker": "Drupal Partners (CMS)",
#       "extra_rules": [
#           {"property": "tag", "operator": "EQ", "value": "Drupal"},
#           {"property": "tag", "operator": "EQ", "value": "BinaryWorks"},
#       ],
#       "logo": None,
#   },
#
# Trade-off: the overlap maths needs to express (A1 or A2) AND (B1 or B2) as a
# cartesian product of HubSpot filter groups, and HubSpot allows only 5 groups
# per search. With one rule per brand every intersection fits. Add extra rules
# and the three-way intersection stops fitting, so the overlap panel will say so
# rather than print a wrong number.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2. TRACKED FIELDS
# ---------------------------------------------------------------------------
# One entry per field you want a total count and a blank count for.
#
#   label     : what shows on the dashboard.
#   contacts  : internal property name, or None to resolve it from the label.
#
# A None (or a name that does not exist in your portal) is not fatal. On startup
# the app pulls your real property list and tries to match the label, so a custom
# field called "Industry Segment" is found even if its internal name is
# "industry_segment_2". Anything it still cannot find is shown as "n/a" and left
# out of the maths, never counted as 100% blank.

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

# Digit grouping in the dashboard. "en-US" gives 411,600. "en-IN" gives
# 4,11,600, which is what the old lead dashboard used. HubSpot's own UI shows
# en-US, so that is the default: the numbers here line up with the numbers you
# see when you go and check a count in HubSpot.
NUMBER_LOCALE = "en-US"

GREEN_AT = 90   # completion at or above this is green
AMBER_AT = 70   # completion at or above this is amber, below it is red

# Count the contacts that sit in more than one brand. Costs 4 extra API calls
# (three pairs and the triple). Set False to skip it.
SHOW_OVERLAP = True

# HubSpot caps the CRM Search API at 5 requests per second, shared across the
# whole account and every search endpoint. 3.0 leaves headroom.
SEARCH_RATE_PER_SEC = 3.0

CACHE_TTL_SECONDS = 1800  # 30 minutes
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
