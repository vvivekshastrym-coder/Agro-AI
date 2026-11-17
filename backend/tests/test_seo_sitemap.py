"""Validation tests for SEO Phase 2: public routes, guides, structured data, sitemap.xml, and robots.txt."""
import pathlib
import re
import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ROOT = pathlib.Path(__file__).resolve().parents[2]
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def test_sitemap_xml_valid_and_all_18_routes_200_with_unique_seo():
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "xml" in r.headers.get("content-type", "")

    root = ET.fromstring(r.text)
    locs = [el.text for el in root.findall("sm:url/sm:loc", NS)]
    lastmods = [el.text for el in root.findall("sm:url/sm:lastmod", NS)]

    assert len(locs) == 18
    assert len(locs) == len(set(locs))  # no duplicates
    assert len(lastmods) == len(locs)

    seen_titles = set()
    seen_descs = set()
    for loc in locs:
        assert loc.startswith("https://agroai.live/"), loc
        assert "localhost" not in loc and "127.0.0.1" not in loc
        path = loc.replace("https://agroai.live", "") or "/"
        page = client.get(path, follow_redirects=False)
        assert page.status_code == 200, f"{path} returned {page.status_code}"

        canonical = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', page.text)
        assert canonical and canonical.group(1) == loc, f"Canonical mismatch on {path}"

        title = re.search(r"<title>(.*?)</title>", page.text, re.S)
        desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', page.text)
        assert title and desc
        assert title.group(1) not in seen_titles, f"Duplicate title on {path}"
        assert desc.group(1) not in seen_descs, f"Duplicate description on {path}"
        seen_titles.add(title.group(1))
        seen_descs.add(desc.group(1))


def test_structured_data_present_on_app_routes_and_articles():
    for path in ["/diagnose", "/agrogpt", "/weather", "/mandi", "/plans", "/about", "/contact"]:
        html_text = client.get(path).text
        assert '"@type": "Organization"' in html_text
        assert '"@type": "WebSite"' in html_text
        assert '"@type": "WebPage"' in html_text
        assert '"@type": "BreadcrumbList"' in html_text

    for guide in [
        "/guides/crop-diseases",
        "/guides/crop-cultivation",
        "/guides/weather-advisories",
        "/guides/mandi-markets",
        "/guides/soil-and-fertilizers",
        "/guides/farmer-resources",
    ]:
        html_text = client.get(guide).text
        assert '"@type": "Article"' in html_text
        assert '"@type": "BreadcrumbList"' in html_text
        assert "fonts.googleapis.com" not in html_text


def test_sitemap_excludes_private_and_authenticated_routes():
    xml_text = client.get("/sitemap.xml").text
    for forbidden in ["/admin", "/api/", "/delete-account", "/docs", "/redoc", "/login", "/auth"]:
        assert forbidden not in xml_text


def test_robots_txt_allows_public_blocks_private_and_links_sitemap():
    r = client.get("/robots.txt")
    assert r.status_code == 200
    txt = r.text
    assert "Sitemap: https://agroai.live/sitemap.xml" in txt
    for blocked in ["Disallow: /admin", "Disallow: /api/", "Disallow: /delete-account"]:
        assert blocked in txt
    for asset_prefix in ["/css", "/js", "/icons", "/fonts"]:
        assert f"Disallow: {asset_prefix}" not in txt


def test_static_generated_dist_seo_files_exist():
    for rel in [
        "sitemap.xml",
        "dist/sitemap.xml",
        "dist/robots.txt",
        "dist/diagnose.html",
        "dist/agrogpt.html",
        "dist/weather.html",
        "dist/mandi.html",
        "dist/plans.html",
        "dist/about.html",
        "dist/contact.html",
        "dist/guides.html",
        "dist/guides/crop-diseases.html",
    ]:
        assert (ROOT / rel).is_file(), f"Missing {rel}"
    ET.fromstring((ROOT / "sitemap.xml").read_text(encoding="utf-8"))
