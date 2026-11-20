"""AgroGPT Mandatory Authentication and Guest Access Restriction Test Suite.
Validates that AgroGPT is strictly inaccessible to guest sessions and unauthenticated requests,
while ensuring conversation privacy and ownership, and leaving public endpoints accessible.
"""
import os, sys, time, uuid
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.main import app
from app.auth import deps
from app.database.connection import SessionLocal
from app.database.models import User, UserRole, AgroGPTConversation, AgroGPTMessage

_KEY = ec.generate_private_key(ec.SECP256R1())

class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class K: key = _KEY.public_key()
        return K()

@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    monkeypatch.setattr(deps, "_get_jwks_client", lambda: _FakeJWKS())

client = TestClient(app)

def create_user_token(sub: str, email: str = None, phone: str = None, is_guest: bool = False):
    claims = {
        "sub": sub,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iss": "https://example.invalid/auth/v1",
        "user_metadata": {
            "name": f"User {sub}",
            "is_guest": is_guest,
        }
    }
    if email:
        claims["email"] = email
    if phone:
        claims["phone"] = phone
    return jwt.encode(claims, _KEY, algorithm="ES256")

def test_no_auth_header_rejected_with_401():
    endpoints = [
        ("post", "/api/agro-gpt/chat", {"message": "hello"}),
        ("post", "/api/agro-gpt/chat/stream", {"message": "hello"}),
        ("get", "/api/agro-gpt/conversations", None),
        ("get", "/api/agro-gpt/conversations/conv-123", None),
        ("delete", "/api/agro-gpt/conversations/conv-123", None),
        ("get", "/api/agro-gpt/daily-digest", None),
        ("post", "/api/agro-gpt/context/diagnosis", {"report_id": "rep-123"}),
    ]
    for method, path, payload in endpoints:
        if method == "post":
            resp = client.post(path, json=payload)
        elif method == "get":
            resp = client.get(path)
        elif method == "delete":
            resp = client.delete(path)
        assert resp.status_code == 401, f"{method.upper()} {path} allowed without auth!"
        data = resp.json()
        assert "error" in data or "detail" in data

def test_guest_session_token_rejected_with_401():
    # 1. Obtain a real guest session token from the guest session endpoint
    guest_res = client.post("/api/auth/guest-session")
    assert guest_res.status_code == 200
    guest_token = guest_res.json()["access_token"]
    guest_headers = {"Authorization": f"Bearer {guest_token}"}

    # 2. Verify all AgroGPT endpoints reject this guest session with 401 GUEST_ACCESS_DENIED
    endpoints = [
        ("post", "/api/agro-gpt/chat", {"message": "help with my tomato crop"}),
        ("post", "/api/agro-gpt/chat/stream", {"message": "pest alert"}),
        ("get", "/api/agro-gpt/conversations", None),
        ("get", "/api/agro-gpt/conversations/conv-fake", None),
        ("delete", "/api/agro-gpt/conversations/conv-fake", None),
        ("get", "/api/agro-gpt/daily-digest", None),
        ("post", "/api/agro-gpt/context/diagnosis", {"report_id": "rep-fake"}),
    ]
    for method, path, payload in endpoints:
        if method == "post":
            resp = client.post(path, json=payload, headers=guest_headers)
        elif method == "get":
            resp = client.get(path, headers=guest_headers)
        elif method == "delete":
            resp = client.delete(path, headers=guest_headers)
        assert resp.status_code == 401, f"Guest access permitted to {method.upper()} {path}!"
        data = resp.json()
        err_code = data.get("detail", {}).get("error", {}).get("code")
        assert err_code == "GUEST_ACCESS_DENIED"

def test_authenticated_farmer_access_and_conversation_isolation():
    farmer_a_id = f"farmer_a_{uuid.uuid4().hex[:8]}"
    farmer_b_id = f"farmer_b_{uuid.uuid4().hex[:8]}"

    # Seed authenticated users in DB
    db = SessionLocal()
    user_a = User(
        id=farmer_a_id,
        phone="+919876543210",
        full_name="Farmer Ramesh",
        role=UserRole.farmer,
        is_verified=True,
    )
    user_b = User(
        id=farmer_b_id,
        phone="+919876543211",
        full_name="Farmer Suresh",
        role=UserRole.farmer,
        is_verified=True,
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()

    token_a = create_user_token(farmer_a_id, phone="+919876543210")
    token_b = create_user_token(farmer_b_id, phone="+919876543211")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Farmer A sends chat message
    chat_resp = client.post("/api/agro-gpt/chat", json={
        "message": "What is the best fertilizer for tomato?",
        "language": "en"
    }, headers=headers_a)
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "reply" in chat_data
    conv_id = chat_data["conversation_id"]

    # 2. Farmer A lists conversations: conv_id must be present
    list_a = client.get("/api/agro-gpt/conversations", headers=headers_a)
    assert list_a.status_code == 200
    a_conv_ids = [c["id"] for c in list_a.json()["conversations"]]
    assert conv_id in a_conv_ids

    # 3. Farmer B lists conversations: Farmer A's conv_id must NOT be present
    list_b = client.get("/api/agro-gpt/conversations", headers=headers_b)
    assert list_b.status_code == 200
    b_conv_ids = [c["id"] for c in list_b.json()["conversations"]]
    assert conv_id not in b_conv_ids

    # 4. Farmer B attempts to get Farmer A's conversation: 403 Forbidden
    detail_b = client.get(f"/api/agro-gpt/conversations/{conv_id}", headers=headers_b)
    assert detail_b.status_code == 403

    # 5. Farmer B attempts to delete Farmer A's conversation: 403 Forbidden
    del_b = client.delete(f"/api/agro-gpt/conversations/{conv_id}", headers=headers_b)
    assert del_b.status_code == 403

    # 6. Farmer A gets own conversation: 200 OK
    detail_a = client.get(f"/api/agro-gpt/conversations/{conv_id}", headers=headers_a)
    assert detail_a.status_code == 200
    assert len(detail_a.json()["messages"]) >= 2  # user + assistant

    # 7. Farmer A deletes own conversation: 200 OK
    del_a = client.delete(f"/api/agro-gpt/conversations/{conv_id}", headers=headers_a)
    assert del_a.status_code == 200
    assert del_a.json()["status"] == "success"

    # 8. Subsequent access by Farmer A returns 404
    detail_a_after = client.get(f"/api/agro-gpt/conversations/{conv_id}", headers=headers_a)
    assert detail_a_after.status_code == 404

    db.close()

def test_public_guest_features_remain_accessible():
    # Mandi market prices and weather must remain accessible for guests
    mandi_resp = client.get("/api/market/mandi?commodity=Tomato")
    assert mandi_resp.status_code == 200

    states_resp = client.get("/api/market/states")
    assert states_resp.status_code == 200
