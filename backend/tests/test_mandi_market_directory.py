import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_mandi_states_list():
    resp = client.get("/api/market/states")
    assert resp.status_code == 200
    data = resp.json()
    assert "states" in data
    assert data["total_states"] >= 8
    states_dict = {s["state"]: s["market_count"] for s in data["states"]}
    assert "Karnataka" in states_dict
    assert states_dict["Karnataka"] >= 30  # Demonstrating far more than 4 or 5 markets

def test_mandi_districts_list():
    resp = client.get("/api/market/districts?state=Karnataka")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "Karnataka"
    assert "Kolar" in data["districts"]
    assert "Bengaluru Urban" in data["districts"]
    assert "Haveri" in data["districts"]
    assert data["total_districts"] >= 20

def test_mandi_commodities_list():
    resp = client.get("/api/market/commodities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_commodities"] >= 15
    comms = data["commodities"]
    assert "Tomato" in comms
    assert "Onion" in comms
    assert "Chilli (Red)" in comms or "Chilli" in str(comms)

def test_mandi_markets_pagination_and_count():
    # Test page 1 with limit 15 for Karnataka
    resp = client.get("/api/market/markets?state=Karnataka&page=1&limit=15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 40  # Karnataka has ~50 genuine APMC markets in directory
    assert data["page"] == 1
    assert data["limit"] == 15
    assert len(data["records"]) == 15
    assert data["has_more"] is True

    # Test page 2 (pagination returns different records without duplicate IDs)
    resp2 = client.get("/api/market/markets?state=Karnataka&page=2&limit=15")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["page"] == 2
    assert len(data2["records"]) == 15
    ids_p1 = {r["id"] for r in data["records"]}
    ids_p2 = {r["id"] for r in data2["records"]}
    assert len(ids_p1.intersection(ids_p2)) == 0  # No duplicates between pages!

def test_mandi_markets_search():
    # Search for Byadgi chilli market
    resp = client.get("/api/market/markets?q=Byadgi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("Byadgi" in r["market_name"] for r in data["records"])
    assert data["records"][0]["state"] == "Karnataka"
    assert data["records"][0]["district"] == "Haveri"

    # Search for Lasalgaon in Maharashtra
    resp2 = client.get("/api/market/markets?q=Lasalgaon")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] >= 1
    assert "Lasalgaon APMC" in data2["records"][0]["market_name"]
    assert data2["records"][0]["state"] == "Maharashtra"

def test_separate_market_and_price_availability():
    # 1. Market with verified price observation (e.g. Kolar APMC + Tomato)
    resp1 = client.get("/api/market/prices?market_name=Kolar APMC&commodity=Tomato&state=Karnataka")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["available"] is True
    assert len(data1["records"]) >= 1
    assert data1["records"][0]["modal_price"] > 0
    assert "metadata" in data1["records"][0]

    # 2. Market in master directory without current price observation (e.g. Sagar APMC + Tomato)
    resp2 = client.get("/api/market/prices?market_name=Sagar APMC&commodity=Tomato&state=Karnataka")
    assert resp2.status_code == 200
    data2 = resp2.json()
    # Separated: market exists, but prices are absent -> Truthful reporting
    assert data2["available"] is False
    assert data2["message"] == "No current price data available for this market."
    assert data2["records"] == []


def test_karnataka_priority_markets_and_compare_and_csv():
    for q in ["Mandya", "Mysuru", "Maddur", "Nagamangala", "Pandavapura", "KR Market"]:
        r = client.get(f"/api/market/markets?state=Karnataka&q={q}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1, f"Missing Karnataka priority market: {q}"

    cmp_res = client.get("/api/market/compare?commodity=Tomato&state=Karnataka")
    assert cmp_res.status_code == 200
    assert cmp_res.json()["available"] is True
    assert cmp_res.json()["latest_observation_date"] is not None

    csv_res = client.get("/api/market/export.csv?state=Karnataka&commodity=Tomato")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "Commodity,Variety,Mandi,District" in csv_res.text

    # Filtered CSV by specific market
    csv_filtered = client.get("/api/market/export.csv?state=Karnataka&commodity=Tomato&market=Kolar%20APMC")
    assert csv_filtered.status_code == 200
    filtered_lines = [line.strip() for line in csv_filtered.text.strip().splitlines() if line.strip()]
    assert len(filtered_lines) >= 2  # header + at least 1 record
    for row in filtered_lines[1:]:
        assert "Kolar" in row
        assert "Yeshwanthpur" not in row

    # Export for a market date with no observations must NOT leak other dates or markets
    csv_nodata = client.get("/api/market/export.csv?state=Karnataka&commodity=Tomato&market=Kolar%20APMC&market_date=2024-01-01")
    assert csv_nodata.status_code == 200
    nodata_lines = [line.strip() for line in csv_nodata.text.strip().splitlines() if line.strip()]
    assert len(nodata_lines) == 1  # Only the CSV header row
    assert "Commodity,Variety,Mandi,District" in nodata_lines[0]
