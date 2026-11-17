"""Reliability tests for Agro AI Mart checkout.

Covers defects found in the audit of ``place_mart_order``:
  * two buyers racing for the last unit must not both succeed (no overselling)
  * a duplicate submission carrying the same Idempotency-Key must not create a
    second order or take stock twice
  * a failed order must leave stock untouched (no partial writes)
"""
import os, sys, time, uuid, threading
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import MartSellerProfile, MartListing, MartOrder, MartOrderItem

_KEY = ec.generate_private_key(ec.SECP256R1())


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K:
            key = _KEY.public_key()
        return K()


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())


client = TestClient(app)


def _auth(sub):
    claims = {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600, "email": f"{sub}@farm.test"}
    return {"Authorization": f"Bearer {jwt.encode(claims, _KEY, algorithm='ES256')}"}


def _make_listing(stock):
    db = SessionLocal()
    s_id, l_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(MartSellerProfile(id=s_id, user_id=str(uuid.uuid4()), farm_name=f"Farm {s_id[:4]}",
                             contact_phone="9000000009", state="KA", district="Mandya",
                             village="V", status="APPROVED"))
    db.add(MartListing(id=l_id, seller_id=s_id, catalog_item_id="itm_tomato", title="Race Tomatoes",
                       price_minor=3000, unit="kg", stock_quantity=stock,
                       harvest_date="2026-10-14", status="APPROVED"))
    db.commit()
    db.close()
    return l_id


def _order_body(listing_id, qty):
    return {"items": [{"listing_id": listing_id, "quantity": qty}], "fulfilment_type": "PICKUP",
            "delivery_address": {"line": "Pickup at farm"}, "delivery_pincode": "571401"}


def _stock(listing_id):
    db = SessionLocal()
    try:
        return db.query(MartListing).filter(MartListing.id == listing_id).first().stock_quantity
    finally:
        db.close()


def test_oversell_prevented_even_when_race_window_is_widened(monkeypatch):
    """Fault injection: sleep between the stock check and the commit so that every
    concurrent request has already passed its availability check. A correct
    implementation must still sell the last unit exactly once."""
    from app.routers import mart as mart_module
    real_order = mart_module.MartOrder

    def slow_order(*a, **kw):
        time.sleep(0.15)
        return real_order(*a, **kw)

    monkeypatch.setattr(mart_module, "MartOrder", slow_order)
    l_id = _make_listing(stock=1.0)
    results = []
    barrier = threading.Barrier(6)

    def buy(i):
        barrier.wait()
        r = client.post("/api/mart/orders", headers=_auth(f"wide_{i}_{l_id[:6]}"), json=_order_body(l_id, 1.0))
        results.append(r.status_code)

    threads = [threading.Thread(target=buy, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert results.count(200) == 1, f"OVERSOLD: {results.count(200)} orders succeeded for 1 unit: {results}"
    assert _stock(l_id) == 0.0


def test_concurrent_buyers_cannot_oversell_last_unit():
    """12 different customers race for 1 unit: exactly one may succeed."""
    l_id = _make_listing(stock=1.0)
    results = []
    barrier = threading.Barrier(12)

    def buy(i):
        barrier.wait()
        r = client.post("/api/mart/orders", headers=_auth(f"racer_{i}_{l_id[:6]}"), json=_order_body(l_id, 1.0))
        results.append(r.status_code)

    threads = [threading.Thread(target=buy, args=(i,)) for i in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert results.count(200) == 1, f"expected exactly 1 successful order, got {results}"
    assert all(code in (200, 400, 409) for code in results), f"unexpected statuses: {results}"
    assert _stock(l_id) == 0.0
    db = SessionLocal()
    try:
        assert db.query(MartOrderItem).filter(MartOrderItem.listing_id == l_id).count() == 1
    finally:
        db.close()


def test_stock_never_goes_negative_under_parallel_partial_orders():
    """10 kg of stock, 8 buyers x 2 kg: at most 5 succeed and stock never < 0."""
    l_id = _make_listing(stock=10.0)
    results = []
    barrier = threading.Barrier(8)

    def buy(i):
        barrier.wait()
        r = client.post("/api/mart/orders", headers=_auth(f"part_{i}_{l_id[:6]}"), json=_order_body(l_id, 2.0))
        results.append(r.status_code)

    threads = [threading.Thread(target=buy, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    ok = results.count(200)
    assert ok <= 5, f"oversold: {ok} successful orders of 2kg from 10kg stock"
    assert _stock(l_id) == 10.0 - 2.0 * ok
    assert _stock(l_id) >= 0


def test_duplicate_submission_with_idempotency_key_creates_one_order():
    """A retried/double-tapped request with the same key returns the SAME order."""
    l_id = _make_listing(stock=10.0)
    headers = {**_auth(f"idem_{l_id[:6]}"), "Idempotency-Key": f"key-{uuid.uuid4()}"}
    first = client.post("/api/mart/orders", headers=headers, json=_order_body(l_id, 3.0))
    second = client.post("/api/mart/orders", headers=headers, json=_order_body(l_id, 3.0))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert _stock(l_id) == 7.0  # taken once, not twice


def test_same_idempotency_key_with_different_payload_is_rejected():
    l_id = _make_listing(stock=10.0)
    headers = {**_auth(f"idem2_{l_id[:6]}"), "Idempotency-Key": f"key-{uuid.uuid4()}"}
    assert client.post("/api/mart/orders", headers=headers, json=_order_body(l_id, 1.0)).status_code == 200
    reuse = client.post("/api/mart/orders", headers=headers, json=_order_body(l_id, 5.0))
    assert reuse.status_code == 409
    assert _stock(l_id) == 9.0


def test_idempotency_key_is_scoped_per_user():
    """Another customer reusing someone's key must not receive their order."""
    l_id = _make_listing(stock=10.0)
    key = f"key-{uuid.uuid4()}"
    a = client.post("/api/mart/orders", headers={**_auth(f"ua_{l_id[:6]}"), "Idempotency-Key": key}, json=_order_body(l_id, 1.0))
    b = client.post("/api/mart/orders", headers={**_auth(f"ub_{l_id[:6]}"), "Idempotency-Key": key}, json=_order_body(l_id, 1.0))
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["id"] != b.json()["id"]
    assert _stock(l_id) == 8.0


def test_failed_order_leaves_stock_untouched():
    """Second item is unavailable: the first item's stock must NOT be decremented."""
    good = _make_listing(stock=5.0)
    db = SessionLocal()
    seller_id = db.query(MartListing).filter(MartListing.id == good).first().seller_id
    bad = str(uuid.uuid4())
    db.add(MartListing(id=bad, seller_id=seller_id, catalog_item_id="itm_onion", title="Paused Onions",
                       price_minor=2000, unit="kg", stock_quantity=5.0, harvest_date="2026-10-14", status="PAUSED"))
    db.commit(); db.close()

    r = client.post("/api/mart/orders", headers=_auth(f"fail_{good[:6]}"), json={
        "items": [{"listing_id": good, "quantity": 2.0}, {"listing_id": bad, "quantity": 1.0}],
        "fulfilment_type": "PICKUP", "delivery_address": {"line": "x"}, "delivery_pincode": "571401"})
    assert r.status_code == 400
    assert _stock(good) == 5.0


def test_duplicate_listing_lines_cannot_bypass_stock_check():
    """Same listing sent twice (3kg + 3kg) against 5kg stock must be rejected."""
    l_id = _make_listing(stock=5.0)
    r = client.post("/api/mart/orders", headers=_auth(f"dup_{l_id[:6]}"), json={
        "items": [{"listing_id": l_id, "quantity": 3.0}, {"listing_id": l_id, "quantity": 3.0}],
        "fulfilment_type": "PICKUP", "delivery_address": {"line": "x"}, "delivery_pincode": "571401"})
    assert r.status_code == 400
    assert _stock(l_id) == 5.0
