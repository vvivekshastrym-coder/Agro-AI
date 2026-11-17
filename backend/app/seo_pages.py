"""Authoritative SEO route registry, HTML metadata renderer, agricultural guides, and sitemap builder."""
import datetime
import html
import json
import os
import re
from typing import Dict, List, Optional

BASE_URL = "https://agroai.live"
OG_IMAGE = f"{BASE_URL}/icons/icon-512x512.png"

APP_SEO_ROUTES: Dict[str, dict] = {
    "/diagnose": {
        "name": "Crop Disease Diagnosis",
        "title": "Crop Disease Diagnosis — Agro AI",
        "description": "Analyze crop leaf photos and learn about common plant diseases, scouting practices, and pathology guidance on Agro AI.",
        "changefreq": "weekly",
        "priority": "0.9",
    },
    "/agrogpt": {
        "name": "Agro GPT",
        "title": "Agro GPT Multilingual Assistant — Agro AI",
        "description": "Ask practical farming questions in your language with Agro GPT text assistance on Agro AI.",
        "changefreq": "weekly",
        "priority": "0.9",
    },
    "/weather": {
        "name": "Weather Intelligence",
        "title": "Farm Weather Intelligence — Agro AI",
        "description": "Check live local weather forecasts, rainfall outlook, and spray-window advisories for your farm.",
        "changefreq": "daily",
        "priority": "0.9",
    },
    "/mandi": {
        "name": "Mandi Market Prices",
        "title": "Mandi Market Prices — Agro AI",
        "description": "Explore APMC mandi market prices, crop arrivals, and daily price trends across Indian agricultural markets.",
        "changefreq": "daily",
        "priority": "0.9",
    },
    "/plans": {
        "name": "Plans & Pricing",
        "title": "Subscription Plans & Pricing — Agro AI",
        "description": "View Agro AI free and paid membership plans with transparent billing terms, GST disclosure, and easy cancellation.",
        "changefreq": "weekly",
        "priority": "0.8",
    },
    "/about": {
        "name": "About Agro AI",
        "title": "About Agro AI — Smart Farming Platform",
        "description": "Learn how Agro AI supports farmers with weather intelligence, mandi market prices, crop diagnosis, and multilingual advisory tools.",
        "changefreq": "monthly",
        "priority": "0.7",
    },
    "/contact": {
        "name": "Contact & Support",
        "title": "Contact & Farmer Support — Agro AI",
        "description": "Contact Agro AI support and our Grievance Officer for help with accounts, billing, privacy, or parental consent.",
        "changefreq": "monthly",
        "priority": "0.6",
    },
}

GUIDE_ARTICLES: Dict[str, dict] = {
    "/guides/crop-diseases": {
        "name": "Crop Disease Guides",
        "title": "Crop Disease & Leaf Scouting Guide — Agro AI",
        "description": "Practical guide to spotting early leaf spots, blights, rusts, and nutrient deficiencies in Indian crops.",
        "published": "2026-11-17T00:00:00Z",
        "cta_path": "/diagnose",
        "cta_label": "Open Crop Diagnosis Tool",
        "sections": [
            ("Why Early Leaf Scouting Matters", "Walking fields twice a week helps spot fungal lesions, powdery mildew, and pest feeding before symptoms spread across the whole plot."),
            ("How to Take a Clear Diagnostic Photo", "Capture a well-lit, focused photo of a single affected leaf against a plain background, avoiding harsh shadows or motion blur."),
            ("Preventive Field Hygiene", "Remove severely infected plant debris, avoid overhead irrigation late in the evening, and rotate non-host crops between seasons."),
        ],
    },
    "/guides/crop-cultivation": {
        "name": "Crop Cultivation Guides",
        "title": "Seasonal Crop Cultivation Guide — Agro AI",
        "description": "Core sowing, spacing, irrigation scheduling, and weed-management principles for Kharif and Rabi crops.",
        "published": "2026-11-17T00:00:00Z",
        "cta_path": "/agrogpt",
        "cta_label": "Ask Agro GPT About Your Crop",
        "sections": [
            ("Seed Selection & Seedbed Preparation", "Use certified, region-adapted varieties and prepare a well-drained seedbed before monsoon onset or Rabi sowing."),
            ("Critical Irrigation Stages", "Prioritize moisture during germination, flowering, and grain or fruit filling while avoiding waterlogging."),
            ("Integrated Weed & Pest Management", "Timely inter-cultivation in the first 30 days after sowing reduces competition for water and nutrients."),
        ],
    },
    "/guides/weather-advisories": {
        "name": "Weather Advisory Articles",
        "title": "Farm Weather Advisory Guide — Agro AI",
        "description": "How to use local temperature, humidity, wind speed, and rain forecasts to plan spraying and harvesting.",
        "published": "2026-11-17T00:00:00Z",
        "cta_path": "/weather",
        "cta_label": "Check Live Farm Weather",
        "sections": [
            ("Planning Safe Spray Windows", "Avoid foliar spraying when wind speeds are high or rain is forecast within 4 to 6 hours to prevent wash-off and drift."),
            ("Humidity & Disease Risk", "Extended high relative humidity paired with moderate temperatures increases fungal spore germination; inspect lower leaves after humid nights."),
            ("Harvest & Drying Decisions", "Schedule harvesting and sun-drying during dry multi-day windows to protect grain quality and reduce post-harvest spoilage."),
        ],
    },
    "/guides/mandi-markets": {
        "name": "Mandi Market Guides",
        "title": "APMC Mandi Market Price Guide — Agro AI",
        "description": "Understanding minimum, maximum, and modal mandi prices to plan harvest timing and transport.",
        "published": "2026-11-17T00:00:00Z",
        "cta_path": "/mandi",
        "cta_label": "View Mandi Prices",
        "sections": [
            ("Reading Min, Max, and Modal Prices", "The modal price represents the rate at which most lots traded that day, making it more useful than extreme high or low quotes."),
            ("Grading & Moisture Impact", "Clean, uniform, properly dried produce consistently fetches closer to the upper mandi band than unsorted lots."),
            ("Comparing Nearby Markets", "Factor in transport cost, loading fees, and transit weight loss before choosing a distant mandi over a local APMC yard."),
        ],
    },
    "/guides/soil-and-fertilizers": {
        "name": "Fertilizer & Soil Information",
        "title": "Soil Health & Balanced Fertilizer Guide — Agro AI",
        "description": "Using soil testing, organic matter, and split nutrient application to support crop yield and soil fertility.",
        "published": "2026-11-17T00:00:00Z",
        "cta_path": "/agrogpt",
        "cta_label": "Get Soil Guidance in Agro GPT",
        "sections": [
            ("Start with a Soil Health Test", "Soil pH, organic carbon, and available NPK/micronutrient levels guide accurate fertilizer dosing and prevent over-application."),
            ("Split Nitrogen Application", "Applying nitrogen in split doses matched to crop growth stages reduces leaching and improves nutrient uptake."),
            ("Organic Matter & Composting", "Incorporating well-decomposed farmyard manure or crop residue improves water retention and beneficial soil microbes."),
        ],
    },
    "/guides/farmer-resources": {
        "name": "Farmer Education Resources",
        "title": "Farmer Education & Digital Safety Resources — Agro AI",
        "description": "Guides on using digital farm tools safely, understanding subscription terms, and protecting farm data.",
        "published": "2026-11-17T00:00:00Z",
        "cta_path": "/about",
        "cta_label": "Learn About Agro AI",
        "sections": [
            ("Using Digital Advisories Responsibly", "Combine digital diagnosis and weather insights with local Krishi Vigyan Kendra (KVK) or agronomist guidance for major crop interventions."),
            ("Understanding Your Data & Privacy", "Agro AI minimizes personal data collection, disables session replay, and gives farmers direct control over consent and account deletion."),
            ("Transparent Membership & Billing", "Review plan quotas, GST disclosure, and one-click cancellation terms anytime in the Plans section."),
        ],
    },
}


def _org_and_website_ld() -> List[dict]:
    return [
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Agro AI",
            "url": f"{BASE_URL}/",
            "logo": OG_IMAGE,
            "email": "vvivekshastrym@gmail.com",
        },
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Agro AI",
            "url": f"{BASE_URL}/",
        },
    ]


def _breadcrumb_ld(items: List[tuple]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": name,
                "item": f"{BASE_URL}{path}",
            }
            for idx, (name, path) in enumerate(items)
        ],
    }


def render_spa_seo_html(route_path: str, project_root: str) -> Optional[str]:
    meta = APP_SEO_ROUTES.get(route_path)
    index_path = os.path.join(project_root, "index.html")
    if not meta or not os.path.isfile(index_path):
        return None
    raw = open(index_path, "r", encoding="utf-8").read()
    canonical = f"{BASE_URL}{route_path}"
    title_esc = html.escape(meta["title"])
    desc_esc = html.escape(meta["description"])

    raw = re.sub(r"<title>.*?</title>", f"<title>{title_esc}</title>", raw, count=1, flags=re.S)
    raw = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{desc_esc}">', raw, count=1)
    raw = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{canonical}">', raw, count=1)
    raw = re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{title_esc}">', raw, count=1)
    raw = re.sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{desc_esc}">', raw, count=1)
    raw = re.sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{canonical}">', raw, count=1)

    ld_items = _org_and_website_ld() + [
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": meta["title"],
            "description": meta["description"],
            "url": canonical,
        },
        _breadcrumb_ld([("Home", "/"), (meta["name"], route_path)]),
    ]
    ld_json = json.dumps(ld_items, ensure_ascii=False)
    raw = re.sub(
        r'<script type="application/ld\+json">[\s\S]*?</script>',
        f'<script type="application/ld+json">{ld_json}</script>',
        raw,
        count=1,
    )
    return raw


def render_guides_index_html() -> str:
    canonical = f"{BASE_URL}/guides"
    title = "Agricultural Guides & Farmer Knowledge Hub — Agro AI"
    desc = "Explore Agro AI guides on crop diseases, seasonal cultivation, weather advisories, APMC mandi markets, and soil health."
    ld_json = json.dumps(
        _org_and_website_ld()
        + [
            {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc, "url": canonical},
            _breadcrumb_ld([("Home", "/"), ("Guides", "/guides")]),
        ],
        ensure_ascii=False,
    )
    cards = "".join(
        f'<div class="card"><h2><a href="{path}">{html.escape(g["title"].replace(" — Agro AI", ""))}</a></h2>'
        f'<p>{html.escape(g["description"])}</p></div>'
        for path, g in GUIDE_ARTICLES.items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Agro AI">
  <meta property="og:locale" content="en_IN">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{OG_IMAGE}">
  <link rel="stylesheet" href="/css/fonts.css">
  <script type="application/ld+json">{ld_json}</script>
  <style>
    body{{font-family:'Inter',system-ui,sans-serif;background:#FFF8EC;color:#1F2A1F;max-width:920px;margin:0 auto;padding:28px 20px;line-height:1.65;}}
    h1,h2{{font-family:'Fraunces',Georgia,serif;color:#1F4D2B;}}
    .bc{{font-size:13px;color:#5B665B;margin-bottom:16px;}}
    .bc a{{color:#1F4D2B;font-weight:600;text-decoration:none;}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;}}
    .card{{background:#fff;border:1px solid #E5DFCF;border-radius:18px;padding:20px;box-shadow:0 2px 10px rgba(31,77,43,0.06);}}
    a{{color:#1F4D2B;}}
  </style>
</head>
<body>
  <nav class="bc" aria-label="Breadcrumb"><a href="/">Home</a> &rsaquo; <span>Guides</span></nav>
  <h1>Agricultural Knowledge &amp; Farmer Guides</h1>
  <p>{html.escape(desc)}</p>
  <div class="grid">{cards}</div>
  <p style="margin-top:24px;"><a href="/">← Back to Agro AI</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p>
</body>
</html>"""


def render_guide_article_html(route_path: str) -> Optional[str]:
    g = GUIDE_ARTICLES.get(route_path)
    if not g:
        return None
    canonical = f"{BASE_URL}{route_path}"
    ld_json = json.dumps(
        _org_and_website_ld()
        + [
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": g["title"],
                "description": g["description"],
                "datePublished": g["published"],
                "dateModified": g["published"],
                "mainEntityOfPage": canonical,
                "author": {"@type": "Organization", "name": "Agro AI"},
                "publisher": {"@type": "Organization", "name": "Agro AI", "logo": {"@type": "ImageObject", "url": OG_IMAGE}},
            },
            _breadcrumb_ld([("Home", "/"), ("Guides", "/guides"), (g["name"], route_path)]),
        ],
        ensure_ascii=False,
    )
    sections_html = "".join(
        f'<div class="card"><h2>{html.escape(h)}</h2><p>{html.escape(body)}</p></div>'
        for h, body in g["sections"]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(g["title"])}</title>
  <meta name="description" content="{html.escape(g["description"])}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Agro AI">
  <meta property="og:locale" content="en_IN">
  <meta property="og:title" content="{html.escape(g["title"])}">
  <meta property="og:description" content="{html.escape(g["description"])}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{OG_IMAGE}">
  <link rel="stylesheet" href="/css/fonts.css">
  <script type="application/ld+json">{ld_json}</script>
  <style>
    body{{font-family:'Inter',system-ui,sans-serif;background:#FFF8EC;color:#1F2A1F;max-width:820px;margin:0 auto;padding:28px 20px;line-height:1.65;}}
    h1,h2{{font-family:'Fraunces',Georgia,serif;color:#1F4D2B;}}
    .bc{{font-size:13px;color:#5B665B;margin-bottom:14px;}}
    .bc a{{color:#1F4D2B;font-weight:600;text-decoration:none;}}
    .card{{background:#fff;border:1px solid #E5DFCF;border-radius:18px;padding:20px;margin-bottom:16px;box-shadow:0 2px 10px rgba(31,77,43,0.06);}}
    .cta{{display:inline-block;background:#1F4D2B;color:#fff;padding:11px 20px;border-radius:999px;text-decoration:none;font-weight:600;margin-top:8px;}}
  </style>
</head>
<body>
  <nav class="bc" aria-label="Breadcrumb"><a href="/">Home</a> &rsaquo; <a href="/guides">Guides</a> &rsaquo; <span>{html.escape(g["name"])}</span></nav>
  <h1>{html.escape(g["title"].replace(" — Agro AI", ""))}</h1>
  <p>{html.escape(g["description"])}</p>
  {sections_html}
  <p><a class="cta" href="{g["cta_path"]}">{html.escape(g["cta_label"])} &rarr;</a></p>
  <p style="margin-top:20px;"><a href="/guides">&larr; All Agricultural Guides</a> · <a href="/">Agro AI Home</a></p>
</body>
</html>"""


def build_sitemap_xml(project_root: str) -> str:
    entries: List[dict] = []

    def _file_lastmod(fname: str) -> str:
        fpath = os.path.join(project_root, fname)
        if os.path.isfile(fpath):
            ts = os.path.getmtime(fpath)
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    index_lm = _file_lastmod("index.html")
    entries.append({"loc": f"{BASE_URL}/", "lastmod": index_lm, "changefreq": "daily", "priority": "1.0"})

    for path, meta in APP_SEO_ROUTES.items():
        entries.append({"loc": f"{BASE_URL}{path}", "lastmod": index_lm, "changefreq": meta["changefreq"], "priority": meta["priority"]})

    seo_mod = _file_lastmod(os.path.join("backend", "app", "seo_pages.py"))
    entries.append({"loc": f"{BASE_URL}/guides", "lastmod": seo_mod, "changefreq": "weekly", "priority": "0.8"})
    for path, g in GUIDE_ARTICLES.items():
        entries.append({"loc": f"{BASE_URL}{path}", "lastmod": g["published"], "changefreq": "monthly", "priority": "0.7"})

    for path, fname, freq, prio in [
        ("/privacy", "privacy.html", "monthly", "0.5"),
        ("/terms", "terms.html", "monthly", "0.5"),
        ("/cookies", "cookies.html", "monthly", "0.4"),
    ]:
        if os.path.isfile(os.path.join(project_root, fname)):
            entries.append({"loc": f"{BASE_URL}{path}", "lastmod": _file_lastmod(fname), "changefreq": freq, "priority": prio})

    xml_rows = "\n".join(
        f"  <url>\n    <loc>{e['loc']}</loc>\n    <lastmod>{e['lastmod']}</lastmod>\n"
        f"    <changefreq>{e['changefreq']}</changefreq>\n    <priority>{e['priority']}</priority>\n  </url>"
        for e in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{xml_rows}\n</urlset>\n'


def write_dist_seo_pages(project_root: str, dist_dir: str) -> None:
    """Materializes static SEO routes & sitemap into dist/ (for Firebase Hosting) and root sitemap.xml."""
    for path in APP_SEO_ROUTES:
        content = render_spa_seo_html(path, project_root)
        if content:
            out_file = os.path.join(dist_dir, path.lstrip("/") + ".html")
            open(out_file, "w", encoding="utf-8").write(content)

    guides_dir = os.path.join(dist_dir, "guides")
    os.makedirs(guides_dir, exist_ok=True)
    open(os.path.join(dist_dir, "guides.html"), "w", encoding="utf-8").write(render_guides_index_html())
    for path in GUIDE_ARTICLES:
        slug = path.split("/")[-1]
        content = render_guide_article_html(path)
        if content:
            open(os.path.join(guides_dir, f"{slug}.html"), "w", encoding="utf-8").write(content)

    sm = build_sitemap_xml(project_root)
    open(os.path.join(project_root, "sitemap.xml"), "w", encoding="utf-8").write(sm)
    open(os.path.join(dist_dir, "sitemap.xml"), "w", encoding="utf-8").write(sm)


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dist = os.path.join(root, "dist")
    if os.path.isdir(dist):
        write_dist_seo_pages(root, dist)
        print("Generated SEO pages and sitemap.xml in dist/")
