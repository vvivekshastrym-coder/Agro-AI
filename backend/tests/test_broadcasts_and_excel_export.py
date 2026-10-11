"""Automated test suite for:
1. Post & Offer creation by workers (draft / pending_approval).
2. Worker blocked from approving posts/offers (Super Admin gate).
3. Super Admin approval & rejection workflow.
4. Public farmer broadcasts feed (GET /api/broadcasts).
5. Farmer registry Excel (.xlsx) and CSV export endpoints.
"""
import os, sys, time, uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)


def test_broadcast_worker_draft_and_super_admin_approval():
    """Worker drafts a promotional offer, Super Admin approves it, verified live in public feed."""
    # 1. Super Admin login
    sa_res = client.post("/api/admin/login", json={
        "email": "vvivekshastrym@gmail.com",
        "password": "Vivek@123"
    })
    sa_token = sa_res.json()["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    # 2. Worker setup and approval
    worker_email = f"content_worker_{uuid.uuid4().hex[:6]}@agroai.internal"
    worker_pwd = "ContentPass@123"
    client.post("/api/admin/request-access", json={
        "email": worker_email,
        "full_name": "Pooja Sharma (Content & Offers)",
        "password": worker_pwd,
        "requested_role": "content_manager"
    })
    reqs = client.get("/api/admin/access-requests", headers=sa_headers).json()
    w_req = next(r for r in reqs if r["email"] == worker_email)
    client.post(f"/api/admin/access-requests/{w_req['id']}/approve", headers=sa_headers, json={"role": "content_manager"})

    # 3. Worker logs in
    w_login = client.post("/api/admin/login", json={"email": worker_email, "password": worker_pwd})
    w_token = w_login.json()["access_token"]
    w_headers = {"Authorization": f"Bearer {w_token}"}

    # 4. Worker creates a promotional offer for farmers (starts in pending_approval or draft)
    post_res = client.post("/api/admin/broadcasts", headers=w_headers, json={
        "item_type": "offer",
        "title": "Monsoon Fertilizer 25% Off Deal",
        "content": "Special subsidy for organic vermicompost and NPK fertilizers during sowing season.",
        "discount_percent": 25.0,
        "discount_code": "MONSOON25",
        "tags": ["fertilizer", "monsoon", "discount"],
        "submit_for_approval": True
    })
    assert post_res.status_code == 200
    item_id = post_res.json()["id"]
    assert post_res.json()["status"] == "pending_approval"

    # 5. Worker CANNOT approve the post -> strictly requires Super Admin
    worker_approve_fail = client.post(f"/api/admin/broadcasts/{item_id}/approve", headers=w_headers)
    assert worker_approve_fail.status_code == 403
    assert worker_approve_fail.json()["detail"]["error"]["code"] == "INSUFFICIENT_ROLE"

    # 6. Unapproved post is NOT visible in public farmer feed
    pub_res = client.get("/api/broadcasts").json()
    assert not any(p["id"] == item_id for p in pub_res)

    # 7. Super Admin inspects and approves the offer
    approve_ok = client.post(f"/api/admin/broadcasts/{item_id}/approve", headers=sa_headers)
    assert approve_ok.status_code == 200
    assert approve_ok.json()["status"] == "approved"

    # 8. Post is now LIVE in public farmer feed
    pub_res_after = client.get("/api/broadcasts").json()
    approved_post = next(p for p in pub_res_after if p["id"] == item_id)
    assert approved_post["title"] == "Monsoon Fertilizer 25% Off Deal"
    assert approved_post["discount_code"] == "MONSOON25"
    assert approved_post["discount_percent"] == 25.0

    # 9. Also appears in public /api/offers feed
    offers_res = client.get("/api/offers").json()
    assert any(o["id"] == item_id for o in offers_res)


def test_super_admin_reject_broadcast_workflow():
    """Super Admin can reject a post with guidance notes."""
    sa_res = client.post("/api/admin/login", json={"email": "vvivekshastrym@gmail.com", "password": "Vivek@123"})
    sa_headers = {"Authorization": f"Bearer {sa_res.json()['access_token']}"}

    create_res = client.post("/api/admin/broadcasts", headers=sa_headers, json={
        "item_type": "post",
        "title": "Incomplete Pest Alert",
        "content": "Short test advisory note.",
        "submit_for_approval": False
    })
    item_id = create_res.json()["id"]

    # Submit for approval
    sub_res = client.post(f"/api/admin/broadcasts/{item_id}/submit", headers=sa_headers)
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "pending_approval"

    # Super Admin rejects with notes
    rej_res = client.post(f"/api/admin/broadcasts/{item_id}/reject", headers=sa_headers, json={
        "rejection_notes": "Please include specific chemical / organic dosage recommendations before publishing."
    })
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"


def test_farmer_data_excel_and_csv_export():
    """Admin can export all registered farmers into styled Excel (.xlsx) and CSV files."""
    sa_res = client.post("/api/admin/login", json={"email": "vvivekshastrym@gmail.com", "password": "Vivek@123"})
    sa_headers = {"Authorization": f"Bearer {sa_res.json()['access_token']}"}

    # 1. Summary metadata
    summary_res = client.get("/api/admin/export/summary", headers=sa_headers)
    assert summary_res.status_code == 200
    data = summary_res.json()
    assert "total_farmers" in data
    assert data["total_farmers"] > 0
    assert data["file_persisted_on_disk"] is True
    assert "farmers_registry.xlsx" in data["excel_file_path"]

    # 2. Download Excel (.xlsx) file
    excel_res = client.get("/api/admin/export/farmers-excel", headers=sa_headers)
    assert excel_res.status_code == 200
    assert "spreadsheetml" in excel_res.headers["content-type"]
    assert len(excel_res.content) > 1000
    # Check PK zip header of .xlsx format
    assert excel_res.content[:2] == b"PK"

    # 3. Download CSV file
    csv_res = client.get("/api/admin/export/farmers-csv", headers=sa_headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert b"Farmer ID" in csv_res.content or b"full_name" in csv_res.content
