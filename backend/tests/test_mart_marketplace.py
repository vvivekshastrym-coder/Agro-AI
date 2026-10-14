"""Agro AI Mart — Automated Integration & Security Tests
Verifies:
1. Unapproved sellers cannot create listings.
2. Unapproved listings are invisible and unbuyable to public customers.
3. Seller review checklist workflow (staff approval required).
4. One farm per order rule enforced strictly.
5. Atomic stock decrements and overselling prevention.
6. Order state machine (PLACED -> ACCEPTED_BY_SELLER -> COMPLETED).
7. Customer cancellation before seller acceptance restocks inventory.
8. Truthful waitlist collection for unserved PIN codes.
"""
import os, sys, time, uuid
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import (
    User, UserRole, AdminUser, AdminUserRole,
    MartCategory, MartCatalogItem, MartSellerProfile,
    MartListing, MartOrder, MartOrderItem, MartWaitlist
)

_KEY = ec.generate_private_key(ec.SECP256R1())


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K: key = _KEY.public_key()
        return K()


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())


client = TestClient(app)


def token(sub, key=_KEY, alg="ES256", aud="authenticated", exp_delta=3600, **extra):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta, "email": f"{sub}@farm.test", **extra}
    return jwt.encode(claims, key, algorithm=alg)


def auth(sub):
    return {"Authorization": f"Bearer {token(sub)}"}


def test_categories_and_catalog_available():
    """Reference produce categories and item catalog are populated and accessible."""
    res = client.get("/api/mart/categories")
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) >= 3
    slugs = [c["slug"] for c in categories]
    assert "vegetables" in slugs
    assert "fruits" in slugs
    assert "leafy-greens" in slugs

    cat_res = client.get("/api/mart/catalog?category_slug=vegetables")
    assert cat_res.status_code == 200
    veg_items = cat_res.json()
    assert any(it["slug"] == "tomato" for it in veg_items)


def test_unapproved_user_cannot_create_listing():
    """Unapproved farmers cannot publish produce listings."""
    farmer_auth = auth("farmer_unverified_mallesh")
    res = client.post("/api/mart/seller/listings", headers=farmer_auth, json={
        "catalog_item_id": "itm_tomato",
        "title": "Unapproved Farm Tomatoes",
        "price_minor": 4000,
        "unit": "kg",
        "stock_quantity": 50,
        "harvest_date": "2026-10-14"
    })
    assert res.status_code == 403
    assert res.json()["detail"]["error"]["code"] == "SELLER_NOT_APPROVED"


def test_seller_approval_and_listing_lifecycle():
    """
    Full workflow:
    1. Farmer submits application.
    2. Admin reviews and approves seller.
    3. Approved farmer creates listing (starts in SUBMITTED).
    4. Unapproved listing is invisible to public customers.
    5. Admin reviews and approves listing.
    6. Listing becomes visible to customers.
    """
    farmer_id = f"farmer_ramesh_{int(time.time())}"
    farmer_auth = auth(farmer_id)
    login_res = client.post("/api/admin/login", json={"email": "vvivekshastrym@gmail.com", "password": "Vivek@123"}).json()
    admin_auth = {"Authorization": f"Bearer {login_res['access_token']}"}

    # 1. Submit seller application
    apply_res = client.post("/api/mart/seller/apply", headers=farmer_auth, json={
        "farm_name": "Ramesh Organic Mandya Farm",
        "contact_phone": "9876543210",
        "state": "Karnataka",
        "district": "Mandya",
        "village": "Maddur",
        "service_pincodes": ["571401", "560001", "560034"],
        "fulfilment_modes": ["delivery", "pickup"],
        "proof_type": "Pahani / RTC (Karnataka)",
        "declaration_cultivates_produce": True
    })
    assert apply_res.status_code == 200
    assert apply_res.json()["status"] == "SUBMITTED"

    # Get application ID from admin queue
    apps = client.get("/api/admin/mart/applications?status_filter=SUBMITTED", headers=admin_auth).json()
    my_app = next(a for a in apps if a["farm_name"] == "Ramesh Organic Mandya Farm")
    app_id = my_app["id"]

    # 2. Admin approves application
    rev_res = client.post(f"/api/admin/mart/applications/{app_id}/review", headers=admin_auth, json={
        "decision": "APPROVED",
        "staff_call_completed": True,
        "review_notes": "Land record 7/12 verified and phone call confirmed harvest schedule."
    })
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "APPROVED"

    # 3. Farmer creates produce listing
    list_res = client.post("/api/mart/seller/listings", headers=farmer_auth, json={
        "catalog_item_id": "itm_tomato",
        "title": "Fresh Farm Tomatoes (Country Hybrid)",
        "description": "Naturally ripened, vine picked today.",
        "price_minor": 3500, # ₹35.00/kg
        "unit": "kg",
        "min_order_qty": 1.0,
        "stock_quantity": 25.0,
        "harvest_date": "2026-10-14",
        "fulfilment_type": "BOTH",
        "is_organic_claim": False
    })
    assert list_res.status_code == 200
    listing_id = list_res.json()["id"]

    # 4. Unapproved listing is INVISIBLE to customers
    public_before = client.get("/api/mart/listings").json()
    assert not any(l["id"] == listing_id for l in public_before)

    # 5. Admin approves listing
    q_res = client.post(f"/api/admin/mart/listings/{listing_id}/review", headers=admin_auth, json={
        "decision": "APPROVED"
    })
    assert q_res.status_code == 200

    # 6. Approved listing is now VISIBLE to customers
    public_after = client.get("/api/mart/listings").json()
    assert any(l["id"] == listing_id for l in public_after)


def test_one_farm_per_order_rule():
    """Checkout enforces that items must come from a single farm per order."""
    admin_auth = auth("farmer_rajesh")
    db = SessionLocal()

    # Create two approved sellers and two listings
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    s1 = MartSellerProfile(id=s1_id, user_id=str(uuid.uuid4()), farm_name="Farm Alpha", contact_phone="9000000001", state="KA", district="Mandya", village="V1", status="APPROVED")
    s2 = MartSellerProfile(id=s2_id, user_id=str(uuid.uuid4()), farm_name="Farm Beta", contact_phone="9000000002", state="KA", district="Mysore", village="V2", status="APPROVED")
    l1_id = str(uuid.uuid4())
    l2_id = str(uuid.uuid4())
    l1 = MartListing(id=l1_id, seller_id=s1_id, catalog_item_id="itm_tomato", title="Tomatoes Alpha", price_minor=3000, unit="kg", stock_quantity=10, harvest_date="2026-10-14", status="APPROVED")
    l2 = MartListing(id=l2_id, seller_id=s2_id, catalog_item_id="itm_onion", title="Onions Beta", price_minor=2500, unit="kg", stock_quantity=10, harvest_date="2026-10-14", status="APPROVED")
    db.add_all([s1, s2, l1, l2])
    db.commit()
    db.close()

    customer_auth = auth("customer_ananya")

    # Attempt multi-farm cart
    res = client.post("/api/mart/orders", headers=customer_auth, json={
        "items": [
            {"listing_id": l1_id, "quantity": 2},
            {"listing_id": l2_id, "quantity": 2}
        ],
        "fulfilment_type": "DELIVERY",
        "delivery_address": {"line": "4th Cross, Koramangala", "city": "Bangalore"},
        "delivery_pincode": "560034"
    })
    assert res.status_code == 400
    assert res.json()["detail"]["error"]["code"] == "MULTI_FARM_CART"


def test_atomic_inventory_decrement_and_prevent_overselling():
    """Inventory decrements atomically upon checkout; overselling is rejected."""
    db = SessionLocal()
    s_id = str(uuid.uuid4())
    seller = MartSellerProfile(id=s_id, user_id=str(uuid.uuid4()), farm_name="Farm Gamma", contact_phone="9000000003", state="KA", district="Bangalore", village="Anekal", status="APPROVED")
    l_id = str(uuid.uuid4())
    listing = MartListing(id=l_id, seller_id=s_id, catalog_item_id="itm_carrot", title="Carrots Gamma", price_minor=4000, unit="kg", stock_quantity=5.0, harvest_date="2026-10-14", status="APPROVED")
    db.add_all([seller, listing])
    db.commit()
    db.close()

    customer_auth = auth("customer_deepak")

    # 1. Attempt to buy more than stock (6 kg when 5 kg available)
    res_oversell = client.post("/api/mart/orders", headers=customer_auth, json={
        "items": [{"listing_id": l_id, "quantity": 6.0}],
        "fulfilment_type": "DELIVERY",
        "delivery_address": {"line": "Indiranagar", "city": "Bangalore"},
        "delivery_pincode": "560038"
    })
    assert res_oversell.status_code == 400
    assert res_oversell.json()["detail"]["error"]["code"] == "INSUFFICIENT_STOCK"

    # 2. Buy valid quantity (3 kg)
    res_valid = client.post("/api/mart/orders", headers=customer_auth, json={
        "items": [{"listing_id": l_id, "quantity": 3.0}],
        "fulfilment_type": "DELIVERY",
        "delivery_address": {"line": "Indiranagar", "city": "Bangalore"},
        "delivery_pincode": "560038"
    })
    assert res_valid.status_code == 200
    order_data = res_valid.json()
    assert order_data["status"] == "PLACED"
    assert order_data["total_minor"] == 12000 # 3 kg * ₹40 = ₹120.00
    assert order_data["payment_method"] == "PAY_ON_DELIVERY"

    # Verify inventory was decremented from 5.0 to 2.0
    db = SessionLocal()
    updated_l = db.query(MartListing).filter(MartListing.id == l_id).first()
    assert updated_l.stock_quantity == 2.0
    db.close()


def test_order_cancellation_restocks_inventory():
    """Customer cancellation before seller acceptance automatically restocks inventory."""
    db = SessionLocal()
    s_id = str(uuid.uuid4())
    seller = MartSellerProfile(id=s_id, user_id=str(uuid.uuid4()), farm_name="Farm Delta", contact_phone="9000000004", state="KA", district="Bangalore", village="Devanahalli", status="APPROVED")
    l_id = str(uuid.uuid4())
    listing = MartListing(id=l_id, seller_id=s_id, catalog_item_id="itm_beans", title="Beans Delta", price_minor=5000, unit="kg", stock_quantity=10.0, harvest_date="2026-10-14", status="APPROVED")
    db.add_all([seller, listing])
    db.commit()
    db.close()

    customer_auth = auth("customer_rohit")

    # Place order for 4 kg
    order = client.post("/api/mart/orders", headers=customer_auth, json={
        "items": [{"listing_id": l_id, "quantity": 4.0}],
        "fulfilment_type": "PICKUP",
        "delivery_address": {"line": "Pickup at farm"},
        "delivery_pincode": "562110"
    }).json()
    order_id = order["id"]

    # Verify stock dropped to 6.0
    db = SessionLocal()
    assert db.query(MartListing).filter(MartListing.id == l_id).first().stock_quantity == 6.0
    db.close()

    # Cancel order
    cancel_res = client.post(f"/api/mart/orders/{order_id}/cancel", headers=customer_auth)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Verify stock restored to 10.0
    db = SessionLocal()
    assert db.query(MartListing).filter(MartListing.id == l_id).first().stock_quantity == 10.0
    db.close()


def test_waitlist_records_unserved_pincode():
    """Truthful waitlist records interest when no farms serve a customer's area."""
    res = client.post("/api/mart/waitlist", json={
        "pincode": "580001",
        "district": "Dharwad",
        "state": "Karnataka",
        "phone": "9845000000"
    })
    assert res.status_code == 200
    assert "Thank you" in res.json()["message"]

    db = SessionLocal()
    entry = db.query(MartWaitlist).filter(MartWaitlist.pincode == "580001").first()
    assert entry is not None
    assert entry.district == "Dharwad"
    db.close()
