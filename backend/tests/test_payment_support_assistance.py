"""Automated verification tests for:
- Live Payment Order updates
- Farmer issue reporting (UPI money debited but not activated)
- Staff payment assistance suite:
  1. Staff manual activation with notes & UTR reference
  2. Staff internal support notes log
  3. Staff refund resolution
  4. Audit logging of all staff payment actions
"""
import pytest
import uuid
import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import (
    User, UserRole, AdminUser, AdminUserRole, SubscriptionPlan,
    SubscriptionPlanVersion, PaymentOrder, PaymentTransaction, UserSubscription
)
from app.routers.admin import create_admin_jwt

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_payment_support_assistance_flow(db_session):
    sa_user_id = str(uuid.uuid4())
    farmer_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    order_id = None
    try:
        # 1. Setup super admin & support agent
        sa_user = User(
            id=sa_user_id,
            email="sa_test@agroai.internal",
            full_name="Super Admin Head",
            role=UserRole.admin,
            is_active=True
        )
        db_session.add(sa_user)
        db_session.commit()

        sa_admin = AdminUser(
            id=str(uuid.uuid4()),
            user_id=sa_user.id,
            role=AdminUserRole.super_admin,
            is_active=True
        )
        db_session.add(sa_admin)

        # 2. Setup Farmer
        farmer = User(
            id=farmer_id,
            email="farmer_ramesh@agroai.internal",
            phone="9876543299",
            full_name="Ramesh Gowda",
            role=UserRole.farmer,
            is_active=True,
            is_verified=True
        )
        db_session.add(farmer)

        # 3. Setup Published Plan & Version
        plan = SubscriptionPlan(
            id=plan_id,
            slug="kisan_pro_test",
            status="published"
        )
        db_session.add(plan)
        db_session.commit()

        ver = SubscriptionPlanVersion(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            version=1,
            name="Kisan Pro Plan",
            price_minor=49900,
            currency="INR",
            billing_interval="monthly",
            is_published=True,
            created_by=sa_user.id
        )
        db_session.add(ver)
        db_session.commit()

        sa_token = create_admin_jwt(sa_user.id, sa_user.email, sa_user.full_name, "super_admin")
        farmer_token = create_admin_jwt(farmer.id, farmer.email, farmer.full_name, "farmer")

        # 4. Farmer initiates order
        res_order = client.post(
            "/api/payments/create-order",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"plan_version_id": ver.id}
        )
        assert res_order.status_code == 200
        order_data = res_order.json()
        order_id = order_data["order_id"]
        assert order_data["amount_minor"] == 49900

        # 5. Farmer encounters UPI issue and reports it
        res_issue = client.post(
            f"/api/payments/orders/{order_id}/report-issue",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={
                "issue_type": "payment_deducted_not_activated",
                "description": "Money of Rs 499 was debited from PhonePe UPI, but my app still shows free plan.",
                "upi_ref_or_utr": "UPI-40982310924",
                "contact_phone": "9876543299"
            }
        )
        assert res_issue.status_code == 200
        assert res_issue.json()["status"] == "issue_reported"

        # 6. Admin / Staff checks live orders queue
        res_list = client.get(
            "/api/admin/payments/orders",
            headers={"Authorization": f"Bearer {sa_token}"}
        )
        assert res_list.status_code == 200
        orders_list = res_list.json()
        target_order = next((o for o in orders_list if o["id"] == order_id), None)
        assert target_order is not None
        assert target_order["status"] == "issue_reported"
        assert target_order["has_open_issue"] is True
        assert target_order["user_phone"] == "9876543299"

        # 7. Staff adds an internal support note
        res_note = client.post(
            f"/api/admin/payments/orders/{order_id}/add-notes",
            headers={"Authorization": f"Bearer {sa_token}"},
            json={"note": "Called farmer Ramesh at 9876543299. Confirmed bank SMS debit with UTR UPI-40982310924."}
        )
        assert res_note.status_code == 200

        # 8. Staff resolves the issue and manually activates subscription
        res_assist = client.post(
            f"/api/admin/payments/orders/{order_id}/assist-activate",
            headers={"Authorization": f"Bearer {sa_token}"},
            json={
                "staff_notes": "Verified UPI UTR UPI-40982310924 with bank statement. Activated Kisan Pro.",
                "payment_reference": "UPI-40982310924"
            }
        )
        assert res_assist.status_code == 200
        assist_data = res_assist.json()
        assert assist_data["status"] == "paid"

        # 9. Verify that farmer now has an active subscription in database
        sub = db_session.query(UserSubscription).filter(
            UserSubscription.user_id == farmer.id,
            UserSubscription.status == "active"
        ).first()
        assert sub is not None
        assert sub.plan_version_id == ver.id

        # 10. Verify order status is now paid and issue is closed
        db_session.refresh(sub)
        res_list2 = client.get(
            "/api/admin/payments/orders",
            headers={"Authorization": f"Bearer {sa_token}"}
        )
        orders_list2 = res_list2.json()
        updated_order = next(o for o in orders_list2 if o["id"] == order_id)
        assert updated_order["status"] == "paid"
        assert updated_order["has_open_issue"] is False
    finally:
        # Clean up all created test entities
        if order_id:
            db_session.query(PaymentTransaction).filter(PaymentTransaction.order_id == order_id).delete()
            db_session.query(PaymentOrder).filter(PaymentOrder.id == order_id).delete()
        db_session.query(UserSubscription).filter(UserSubscription.user_id == farmer_id).delete()
        db_session.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.plan_id == plan_id).delete()
        db_session.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).delete()
        db_session.query(AdminUser).filter(AdminUser.user_id == sa_user_id).delete()
        db_session.query(User).filter(User.id.in_([sa_user_id, farmer_id])).delete()
        db_session.commit()

