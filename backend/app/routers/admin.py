"""Agro AI Admin Management API Router
Enforces strict server-side role validation against the admin_users table on every request.
Executive decisions and staff access approvals strictly gated to Head Super Admin (vvivekshastrym@gmail.com).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
import uuid
import time
import jwt
import os
import csv
import io
import json

from ..database.connection import get_db
from ..database.models import (
    User, UserRole, AdminUser, AdminUserRole, SubscriptionPlan, SubscriptionPlanVersion,
    PlanEntitlement, UserSubscription, SubscriptionUsage, PaymentOrder,
    PaymentTransaction, PaymentWebhookEvent, AdminAuditLog, DataRequest, AdminAccessRequest,
    BroadcastItem, BroadcastType, BroadcastStatus, Farm, DiagnosisReport,
    MarketPrice, MandiMarket, MartSellerProfile, MartListing, MartOrder, ExcelImportJob
)
from ..auth.deps import get_current_user, GUEST_SESSION_SECRET
from ..auth.passwords import hash_password, verify_password
from ..services.excel_exporter import fetch_farmer_export_data, generate_farmers_excel_bytes, generate_farmers_csv_bytes, EXPORT_DIR

SUPER_ADMIN_EMAIL = "vvivekshastrym@gmail.com"

router = APIRouter()


# ── 3-TIER ROLE HIERARCHY & GRANULAR PERMISSION MATRIX ─────────────
ADMIN_MODULES = [
    "overview",
    "mart",
    "posts_offers",
    "excel_registry",
    "subscription_plans",
    "users_roles",
    "payment_orders",
    "data_requests",
    "audit_logs",
]

ADMIN_ACTIONS = [
    "read",
    "create",
    "edit",
    "submit",
    "approve",
    "publish",
    "export",
    "suspend",
    "delete",
]

ALL_ACTIONS = list(ADMIN_ACTIONS)

DEFAULT_ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    AdminUserRole.super_admin.value: {m: list(ALL_ACTIONS) for m in ADMIN_MODULES},
    AdminUserRole.admin.value: {
        "overview": ["read"],
        "mart": ["read", "create", "edit", "submit", "approve", "publish", "suspend"],
        "posts_offers": ["read", "create", "edit", "submit", "approve", "publish"],
        "excel_registry": ["read", "create", "edit", "submit", "approve", "publish", "export"],
        "subscription_plans": ["read", "create", "edit", "submit"],
        "users_roles": ["read", "edit", "suspend"],
        "payment_orders": ["read", "edit", "approve"],
        "data_requests": ["read", "create", "edit", "approve"],
        "audit_logs": ["read"],
    },
    AdminUserRole.staff.value: {
        "overview": ["read"],
        "mart": ["read", "create", "edit", "submit"],
        "posts_offers": ["read", "create", "edit", "submit"],
        "excel_registry": ["read", "create", "submit"],
        "subscription_plans": [],
        "users_roles": [],
        "payment_orders": ["read", "edit"],
        "data_requests": ["read", "create", "edit", "submit"],
        "audit_logs": [],
    },
    AdminUserRole.plan_manager.value: {
        "overview": ["read"],
        "mart": ["read"],
        "posts_offers": ["read", "create", "edit", "submit"],
        "excel_registry": ["read", "export"],
        "subscription_plans": ["read", "create", "edit", "submit"],
        "users_roles": [],
        "payment_orders": ["read"],
        "data_requests": [],
        "audit_logs": [],
    },
    AdminUserRole.payment_manager.value: {
        "overview": ["read"],
        "mart": ["read"],
        "posts_offers": ["read"],
        "excel_registry": ["read", "export"],
        "subscription_plans": ["read"],
        "users_roles": [],
        "payment_orders": ["read", "edit", "approve"],
        "data_requests": ["read"],
        "audit_logs": [],
    },
    AdminUserRole.payment_staff.value: {
        "overview": ["read"],
        "mart": [],
        "posts_offers": [],
        "excel_registry": [],
        "subscription_plans": [],
        "users_roles": [],
        "payment_orders": ["read", "edit"],
        "data_requests": [],
        "audit_logs": [],
    },
    AdminUserRole.support_agent.value: {
        "overview": ["read"],
        "mart": ["read"],
        "posts_offers": ["read", "create", "edit", "submit"],
        "excel_registry": ["read", "create", "submit", "export"],
        "subscription_plans": [],
        "users_roles": ["read"],
        "payment_orders": ["read", "edit"],
        "data_requests": ["read", "create", "edit", "submit", "approve"],
        "audit_logs": [],
    },
    AdminUserRole.content_manager.value: {
        "overview": ["read"],
        "mart": ["read"],
        "posts_offers": ["read", "create", "edit", "submit"],
        "excel_registry": ["read", "create", "submit"],
        "subscription_plans": [],
        "users_roles": [],
        "payment_orders": [],
        "data_requests": [],
        "audit_logs": [],
    },
    AdminUserRole.listing_reviewer.value: {
        "overview": ["read"],
        "mart": ["read", "edit", "approve", "publish"],
        "posts_offers": ["read"],
        "excel_registry": ["read"],
        "subscription_plans": [],
        "users_roles": [],
        "payment_orders": [],
        "data_requests": [],
        "audit_logs": [],
    },
    AdminUserRole.seller_reviewer.value: {
        "overview": ["read"],
        "mart": ["read", "edit", "approve"],
        "posts_offers": ["read"],
        "excel_registry": ["read"],
        "subscription_plans": [],
        "users_roles": [],
        "payment_orders": [],
        "data_requests": [],
        "audit_logs": [],
    },
    AdminUserRole.analyst.value: {
        "overview": ["read"],
        "mart": ["read"],
        "posts_offers": ["read"],
        "excel_registry": ["read", "export"],
        "subscription_plans": ["read"],
        "users_roles": ["read"],
        "payment_orders": ["read"],
        "data_requests": ["read"],
        "audit_logs": ["read"],
    },
}


def get_hierarchy_level(admin: AdminUser) -> str:
    """Returns canonical 3-tier hierarchy level: SUPER_ADMIN_HEAD (Level 1), ADMIN (Level 2), or STAFF (Level 3)."""
    if admin.role == AdminUserRole.super_admin:
        return "SUPER_ADMIN_HEAD"
    if admin.role == AdminUserRole.admin:
        return "ADMIN"
    if admin.hierarchy_level in ("SUPER_ADMIN_HEAD", "ADMIN", "STAFF"):
        if admin.hierarchy_level == "SUPER_ADMIN_HEAD" and admin.role != AdminUserRole.super_admin:
            return "ADMIN"
        return admin.hierarchy_level
    return "STAFF"


def get_effective_permissions(admin: AdminUser) -> Dict[str, List[str]]:
    """Computes effective module->actions matrix for an AdminUser, combining role defaults with custom overrides."""
    if admin.role == AdminUserRole.super_admin:
        return {m: list(ALL_ACTIONS) for m in ADMIN_MODULES}
    base = {
        m: list(DEFAULT_ROLE_PERMISSIONS.get(admin.role.value, {}).get(m, []))
        for m in ADMIN_MODULES
    }
    custom = admin.permissions if isinstance(admin.permissions, dict) else {}
    for mod, actions in custom.items():
        if mod in ADMIN_MODULES and isinstance(actions, list):
            valid_acts = [a for a in actions if a in ADMIN_ACTIONS]
            # Hard security boundary: audit_logs can never be deleted or edited
            if mod == "audit_logs":
                valid_acts = [a for a in valid_acts if a == "read"]
            base[mod] = valid_acts
    return base


def has_permission(admin: AdminUser, module: str, action: str) -> bool:
    if admin.role == AdminUserRole.super_admin:
        return True
    perms = get_effective_permissions(admin)
    return action in perms.get(module, [])


def _log_unauthorized_attempt(db: Session, user: Optional[User], role_str: str, reason: str, request: Optional[Request] = None):
    """Records failed or unauthorized administrative access attempts in AdminAuditLog."""
    try:
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None
        path = request.url.path if request else "unknown"
        entry = AdminAuditLog(
            id=str(uuid.uuid4()),
            actor_id=user.id if user else None,
            actor_role=role_str or "unauthenticated",
            action="UNAUTHORIZED_ADMIN_ATTEMPT",
            target_entity="admin_security_gate",
            target_id=path,
            details={"reason": reason, "path": path, "email": user.email if user else None},
            ip_address=ip,
            user_agent=ua,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()


def require_admin(*allowed_roles: AdminUserRole, module: Optional[str] = None, action: Optional[str] = None):
    """Enforces that caller has an active record in admin_users with permitted role or module/action permission."""
    async def _dependency(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AdminUser:
        admin = db.query(AdminUser).filter(AdminUser.user_id == user.id, AdminUser.is_active == True).first()
        if not admin:
            # If user is the designated head super admin, ensure active super admin record
            if user.email and user.email.lower() == SUPER_ADMIN_EMAIL:
                admin = db.query(AdminUser).filter(AdminUser.user_id == user.id).first()
                if not admin:
                    admin = AdminUser(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        role=AdminUserRole.super_admin,
                        hierarchy_level="SUPER_ADMIN_HEAD",
                        is_active=True
                    )
                    db.add(admin)
                else:
                    admin.role = AdminUserRole.super_admin
                    admin.hierarchy_level = "SUPER_ADMIN_HEAD"
                    admin.is_active = True
                db.commit()
                db.refresh(admin)
            else:
                # Allow initial test bootstrap only in non-production environments
                is_prod = os.getenv("ENVIRONMENT", "development").strip().lower() == "production"
                super_admin_count = db.query(AdminUser).filter(AdminUser.role == AdminUserRole.super_admin, AdminUser.is_active == True).count()
                if not is_prod and super_admin_count == 0:
                    admin = AdminUser(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        role=AdminUserRole.super_admin,
                        hierarchy_level="SUPER_ADMIN_HEAD",
                        is_active=True
                    )
                    db.add(admin)
                    db.commit()
                    db.refresh(admin)
                else:
                    _log_unauthorized_attempt(db, user, user.role.value if user.role else "farmer", "No active AdminUser record", request)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"error": {"code": "ADMIN_FORBIDDEN", "message": f"Administrative privileges required. Access must be approved by Head Super Admin ({SUPER_ADMIN_EMAIL})."}}
                    )

        if admin.role == AdminUserRole.super_admin:
            return admin

        # Check explicit module+action permission if specified
        if module and action:
            if has_permission(admin, module, action):
                return admin

        if allowed_roles and admin.role not in allowed_roles:
            # Also check if module+action was granted via custom permissions
            _log_unauthorized_attempt(
                db, user, admin.role.value,
                f"Role {admin.role.value} not in {[r.value for r in allowed_roles]}",
                request
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "INSUFFICIENT_ROLE", "message": f"Required roles: {[r.value for r in allowed_roles]}. Executive decisions require Head Super Admin ({SUPER_ADMIN_EMAIL}) approval."}}
            )

        if module and action and not has_permission(admin, module, action):
            _log_unauthorized_attempt(
                db, user, admin.role.value,
                f"Missing granular permission {module}:{action}",
                request
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "INSUFFICIENT_ROLE", "message": f"Missing required permission '{module}:{action}'."}}
            )

        return admin
    return _dependency


def create_admin_jwt(user_id: str, email: str, full_name: Optional[str], role: str) -> str:
    """Creates a local session token signed by GUEST_SESSION_SECRET accepted by deps.py."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "iss": "agro-ai-local",
        "aud": "authenticated",
        "role": role,
        "iat": now,
        "exp": now + (86400 * 7),  # 7-day token
        "user_metadata": {
            "full_name": full_name or (email.split("@")[0] if email else "Admin"),
            "name": full_name or (email.split("@")[0] if email else "Admin"),
            "email": email,
            "role": role
        }
    }
    return jwt.encode(payload, GUEST_SESSION_SECRET, algorithm="HS256")


_SENSITIVE_AUDIT_KEYS = {"password", "password_hash", "token", "access_token", "refresh_token", "secret", "authorization", "provider_signature"}


def _sanitize_audit_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        out = {}
        for k, v in payload.items():
            if str(k).lower() in _SENSITIVE_AUDIT_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = _sanitize_audit_payload(v)
        return out
    if isinstance(payload, list):
        return [_sanitize_audit_payload(x) for x in payload]
    return payload


def log_admin_action(db: Session, actor: AdminUser, action: str, target_entity: str, target_id: str, details: dict = None, request: Request = None):
    """Writes an immutable server-side audit log entry with automatic secret redaction."""
    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent") if request else None
    safe_details = _sanitize_audit_payload(details or {})
    if isinstance(safe_details, dict):
        safe_details["hierarchy_level"] = get_hierarchy_level(actor)
    log_entry = AdminAuditLog(
        id=str(uuid.uuid4()),
        actor_id=actor.user_id,
        actor_role=actor.role.value,
        action=action,
        target_entity=target_entity,
        target_id=target_id,
        details=safe_details,
        ip_address=ip,
        user_agent=ua
    )
    db.add(log_entry)
    db.commit()


# ── SCHEMAS ───────────────────────────────────────────────────────
class AdminLoginRequest(BaseModel):
    email: str
    password: str

class AccessRequestCreate(BaseModel):
    email: str
    full_name: str
    password: str = Field(..., min_length=6)
    requested_role: str = Field("support_agent")
    notes: Optional[str] = None

class AccessRequestApproveBody(BaseModel):
    role: AdminUserRole = Field(AdminUserRole.support_agent)

class PlanCreateRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9_-]+$")

class VersionCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    price_minor: int = Field(..., ge=0)
    currency: str = Field("INR", max_length=10)
    billing_interval: str = Field(..., pattern=r"^(monthly|quarterly|yearly|lifetime)$")
    trial_days: int = Field(0, ge=0)
    benefits: List[str] = Field(default_factory=list)
    entitlements: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

class PlanStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(draft|published|paused|archived)$")

class RoleAssignRequest(BaseModel):
    user_id: str
    role: Optional[AdminUserRole] = None
    hierarchy_level: Optional[str] = None # SUPER_ADMIN_HEAD, ADMIN, STAFF
    permissions: Optional[Dict[str, List[str]]] = None
    is_active: bool = True


# ── AUTHENTICATION & ACCESS APPROVAL ROUTES ───────────────────────
@router.post("/login")
async def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    """Direct secure admin login with password verification and Super Admin access gate."""
    email_clean = req.email.strip().lower()

    if email_clean == SUPER_ADMIN_EMAIL:
        is_prod = os.getenv("ENVIRONMENT", "development").strip().lower() == "production"
        configured_super_pwd = os.getenv("SUPER_ADMIN_PASSWORD", "" if is_prod else "Vivek@123")
        user = db.query(User).filter(User.email == email_clean).first()
        if not user:
            if is_prod and not configured_super_pwd:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"error": {"code": "ADMIN_NOT_CONFIGURED", "message": "SUPER_ADMIN_PASSWORD must be configured in production."}}
                )
            user = User(
                id=str(uuid.uuid4()),
                email=email_clean,
                full_name="Vivek Shastry (Super Admin)",
                role=UserRole.admin,
                is_active=True,
                is_verified=True,
                password_hash=hash_password(configured_super_pwd)
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        pwd_valid = (bool(configured_super_pwd) and req.password == configured_super_pwd) or (
            bool(user.password_hash) and verify_password(req.password, user.password_hash)
        )
        if not pwd_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid password for Head Super Admin."}}
            )

        if configured_super_pwd and (not user.password_hash or req.password == configured_super_pwd):
            user.password_hash = hash_password(configured_super_pwd)

        admin_rec = db.query(AdminUser).filter(AdminUser.user_id == user.id).first()
        if not admin_rec:
            admin_rec = AdminUser(
                id=str(uuid.uuid4()),
                user_id=user.id,
                role=AdminUserRole.super_admin,
                is_active=True
            )
            db.add(admin_rec)
        else:
            admin_rec.role = AdminUserRole.super_admin
            admin_rec.is_active = True
        db.commit()

        token = create_admin_jwt(user.id, user.email, user.full_name, "super_admin")
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": "super_admin",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name or "Vivek Shastry",
                "role": "super_admin"
            }
        }

    # Other company staff accounts
    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not user.password_hash:
        pending = db.query(AdminAccessRequest).filter(AdminAccessRequest.email == email_clean, AdminAccessRequest.status == "pending").first()
        if pending:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "APPROVAL_REQUIRED", "message": f"Access Denied: Your staff account is awaiting approval from Head Super Admin ({SUPER_ADMIN_EMAIL})."}}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password. Company staff must submit an access request to be approved by Head Super Admin."}}
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}
        )

    admin_rec = db.query(AdminUser).filter(AdminUser.user_id == user.id, AdminUser.is_active == True).first()
    if not admin_rec:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "APPROVAL_REQUIRED", "message": f"Access Denied: Your account has not been approved by Head Super Admin ({SUPER_ADMIN_EMAIL}). Only approved company staff may access the admin panel."}}
        )

    token = create_admin_jwt(user.id, user.email, user.full_name, admin_rec.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": admin_rec.role.value,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": admin_rec.role.value
        }
    }


@router.post("/request-access")
async def request_admin_access(req: AccessRequestCreate, db: Session = Depends(get_db)):
    """Allows company workers to register and submit an access request to the Head Super Admin."""
    email_clean = req.email.strip().lower()
    if email_clean == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail={"error": {"code": "SUPER_ADMIN_EXISTS", "message": "This email belongs to Head Super Admin. Please sign in directly."}})

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email_clean,
            full_name=req.full_name,
            role=UserRole.admin,
            password_hash=hash_password(req.password),
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.password_hash = hash_password(req.password)
        if req.full_name:
            user.full_name = req.full_name
        db.commit()

    existing_req = db.query(AdminAccessRequest).filter(AdminAccessRequest.email == email_clean).first()
    if existing_req:
        if existing_req.status == "approved":
            admin_check = db.query(AdminUser).filter(AdminUser.user_id == user.id, AdminUser.is_active == True).first()
            if admin_check:
                return {"message": "Your account is already approved. You may sign in immediately.", "status": "approved"}
        existing_req.status = "pending"
        existing_req.requested_role = req.requested_role
        existing_req.notes = req.notes
        existing_req.full_name = req.full_name
        existing_req.user_id = user.id
        db.commit()
        return {
            "message": f"Your access request has been updated. Awaiting approval from Head Super Admin ({SUPER_ADMIN_EMAIL}).",
            "status": "pending"
        }

    access_req = AdminAccessRequest(
        id=str(uuid.uuid4()),
        user_id=user.id,
        email=email_clean,
        full_name=req.full_name,
        requested_role=req.requested_role,
        notes=req.notes,
        status="pending"
    )
    db.add(access_req)
    db.commit()

    return {
        "message": f"Access request submitted successfully. Awaiting approval from Head Super Admin ({SUPER_ADMIN_EMAIL}).",
        "status": "pending"
    }


@router.get("/access-requests")
async def list_access_requests(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db)
):
    """Super Admin only: lists pending and processed staff access requests."""
    requests = db.query(AdminAccessRequest).order_by(AdminAccessRequest.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "email": r.email,
            "full_name": r.full_name,
            "requested_role": r.requested_role,
            "notes": r.notes,
            "status": r.status,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in requests
    ]


@router.post("/access-requests/{request_id}/approve")
async def approve_access_request(
    request_id: str,
    req: AccessRequestApproveBody,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Super Admin only: explicitly approves a company worker and grants them an administrative role."""
    req_obj = db.query(AdminAccessRequest).filter(AdminAccessRequest.id == request_id).first()
    if not req_obj:
        raise HTTPException(status_code=404, detail={"error": {"code": "REQUEST_NOT_FOUND", "message": "Access request not found."}})

    user = db.query(User).filter(User.email == req_obj.email).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=req_obj.email,
            full_name=req_obj.full_name,
            role=UserRole.admin,
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    target_tier = "SUPER_ADMIN_HEAD" if req.role == AdminUserRole.super_admin else ("ADMIN" if req.role == AdminUserRole.admin else "STAFF")
    admin_rec = db.query(AdminUser).filter(AdminUser.user_id == user.id).first()
    if not admin_rec:
        admin_rec = AdminUser(
            id=str(uuid.uuid4()),
            user_id=user.id,
            role=req.role,
            hierarchy_level=target_tier,
            is_active=True
        )
        db.add(admin_rec)
    else:
        admin_rec.role = req.role
        admin_rec.hierarchy_level = target_tier
        admin_rec.is_active = True

    req_obj.status = "approved"
    req_obj.reviewed_by = admin.user_id
    req_obj.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(
        db, admin,
        "APPROVE_STAFF_ACCESS",
        "admin_access_requests",
        req_obj.id,
        {"email": req_obj.email, "assigned_role": req.role.value},
        request
    )
    return {
        "status": "approved",
        "email": req_obj.email,
        "role": req.role.value,
        "message": f"Access granted to {req_obj.email} with role {req.role.value}."
    }


@router.post("/access-requests/{request_id}/reject")
async def reject_access_request(
    request_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Super Admin only: rejects a staff access request and deactivates any existing admin access."""
    req_obj = db.query(AdminAccessRequest).filter(AdminAccessRequest.id == request_id).first()
    if not req_obj:
        raise HTTPException(status_code=404, detail={"error": {"code": "REQUEST_NOT_FOUND", "message": "Access request not found."}})

    req_obj.status = "rejected"
    req_obj.reviewed_by = admin.user_id
    req_obj.reviewed_at = datetime.datetime.now(datetime.timezone.utc)

    user = db.query(User).filter(User.email == req_obj.email).first()
    if user:
        admin_rec = db.query(AdminUser).filter(AdminUser.user_id == user.id).first()
        if admin_rec:
            admin_rec.is_active = False

    db.commit()

    log_admin_action(
        db, admin,
        "REJECT_STAFF_ACCESS",
        "admin_access_requests",
        req_obj.id,
        {"email": req_obj.email},
        request
    )
    return {"status": "rejected", "email": req_obj.email}


# ── ROUTES ────────────────────────────────────────────────────────
@router.get("/me")
async def get_admin_profile(admin: AdminUser = Depends(require_admin()), user: User = Depends(get_current_user)):
    """Returns the verified administrative profile of the caller including 3-tier hierarchy level and effective permissions."""
    eff_perms = get_effective_permissions(admin)
    auth_modules = [m for m in ADMIN_MODULES if "read" in eff_perms.get(m, [])]
    return {
        "id": admin.id,
        "user_id": admin.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": admin.role.value,
        "hierarchy_level": get_hierarchy_level(admin),
        "is_super_admin": admin.role == AdminUserRole.super_admin,
        "permissions": eff_perms,
        "authorized_modules": auth_modules,
        "is_active": admin.is_active,
        "created_at": admin.created_at.isoformat() if admin.created_at else None
    }


@router.get("/roles/matrix")
async def get_roles_permission_matrix(admin: AdminUser = Depends(require_admin())):
    """Returns the 3-tier role hierarchy definition, console modules, granular actions, and default permissions."""
    return {
        "hierarchy_tiers": [
            {
                "level": 1,
                "key": "SUPER_ADMIN_HEAD",
                "role": "super_admin",
                "title": "Level 1 — Super Admin Head",
                "owner_email": SUPER_ADMIN_EMAIL,
                "description": "Single authorized platform owner. Controls feature settings, roles, staff permissions, integrations, subscription publishing, marketplace policies, and security configuration.",
            },
            {
                "level": 2,
                "key": "ADMIN",
                "role": "admin",
                "title": "Level 2 — Admin",
                "description": "Manages assigned business modules and supervises staff. Approves posts/offers, reviews Mart listings, oversees Excel imports, and handles operational workflows. Cannot take over owner-level controls.",
            },
            {
                "level": 3,
                "key": "STAFF",
                "role": "staff",
                "title": "Level 3 — Staff",
                "description": "Enters, updates, and validates permitted operational information. Prepares content drafts, uploads validated spreadsheets for review, and handles assigned requests.",
            },
        ],
        "hierarchy_levels": ["SUPER_ADMIN_HEAD", "ADMIN", "STAFF"],
        "modules": ADMIN_MODULES,
        "actions": ADMIN_ACTIONS,
        "default_permissions": DEFAULT_ROLE_PERMISSIONS,
    }


@router.get("/overview/metrics")
async def get_overview_metrics(admin: AdminUser = Depends(require_admin()), db: Session = Depends(get_db)):
    """Computes real live metrics directly from the database across all 9 Admin Console modules."""
    total_users = db.query(User).filter(User.is_test == False, User.is_active == True).count()
    total_farmers = db.query(User).filter(User.role == UserRole.farmer, User.is_test == False, User.is_active == True).count()
    verified_users = db.query(User).filter(User.is_verified == True, User.is_test == False, User.is_active == True).count()
    active_subscriptions = db.query(UserSubscription).filter(UserSubscription.status == "active").count()
    total_orders = db.query(PaymentOrder).count()

    # Calculate revenue from successful transactions
    revenue_res = db.query(func.sum(PaymentTransaction.amount_minor)).filter(PaymentTransaction.status == "success").scalar()
    total_revenue_inr = (revenue_res or 0) / 100.0

    # Real farmland & AI diagnosis operational data
    total_acres = db.query(func.sum(Farm.total_acres)).scalar() or 0.0
    ai_diagnoses = db.query(DiagnosisReport).count()
    active_broadcasts = db.query(BroadcastItem).filter(BroadcastItem.status == BroadcastStatus.approved).count()
    pending_posts_offers = db.query(BroadcastItem).filter(BroadcastItem.status == BroadcastStatus.pending_approval).count()
    pending_staff_requests = db.query(AdminAccessRequest).filter(AdminAccessRequest.status == "pending").count()

    # Mart queues
    pending_farmer_apps = db.query(MartSellerProfile).filter(MartSellerProfile.status.in_(["SUBMITTED", "UNDER_REVIEW"])).count()
    pending_product_approvals = db.query(MartListing).filter(MartListing.status.in_(["SUBMITTED", "UNDER_REVIEW"])).count()

    # Excel Data Registry
    recent_excel_imports = db.query(ExcelImportJob).count()
    pending_excel_imports = db.query(ExcelImportJob).filter(ExcelImportJob.status == "PENDING_REVIEW").count()

    # Subscription Plans & Payments & Data Requests
    published_plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.status == "published").count()
    verified_payments = db.query(PaymentTransaction).filter(PaymentTransaction.status == "success").count()
    pending_financial_tasks = db.query(PaymentOrder).filter(PaymentOrder.status.in_(["failed", "issue_reported"])).count()
    open_data_requests = db.query(DataRequest).filter(DataRequest.status.in_(["pending", "processing", "OPEN", "ASSIGNED", "IN_PROGRESS"])).count()

    pending_approvals = (
        pending_posts_offers +
        pending_staff_requests +
        pending_farmer_apps +
        pending_product_approvals +
        pending_excel_imports
    )

    # Recent audit logs (for Super Admin Head & Admin)
    recent_logs = []
    if has_permission(admin, "audit_logs", "read"):
        logs_q = db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(8).all()
        recent_logs = [
            {
                "id": l.id,
                "actor_id": l.actor_id,
                "actor_role": l.actor_role,
                "action": l.action,
                "target_entity": l.target_entity,
                "target_id": l.target_id,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs_q
        ]

    mandi_markets_count = db.query(MandiMarket).filter(MandiMarket.is_active == True).count()

    return {
        "registered_users": total_users,
        "total_farmers": total_farmers,
        "verified_users": verified_users,
        "active_subscriptions": active_subscriptions,
        "total_orders": total_orders,
        "total_revenue_inr": total_revenue_inr,
        "total_acres": round(float(total_acres), 2),
        "ai_diagnoses_count": ai_diagnoses,
        "active_broadcasts_count": active_broadcasts,
        "published_posts_offers": active_broadcasts,
        "pending_posts_offers": pending_posts_offers,
        "pending_farmer_applications": pending_farmer_apps,
        "pending_product_approvals": pending_product_approvals,
        "recent_excel_imports_count": recent_excel_imports,
        "pending_excel_imports_count": pending_excel_imports,
        "published_subscription_plans_count": published_plans,
        "verified_payments_count": verified_payments,
        "pending_financial_tasks_count": pending_financial_tasks,
        "open_data_requests_count": open_data_requests,
        "pending_approvals_count": pending_approvals,
        "recent_audit_activity": recent_logs,
        "system_status": {
            "database": "Connected",
            "payment_webhook": "Active (/api/payments/webhook)",
            "mandi_directory_markets": mandi_markets_count,
            "weather_provider": "Configured (OpenWeather / Open-Meteo)",
            "super_admin_head": SUPER_ADMIN_EMAIL,
        },
        "payment_gateway_status": "Active (Razorpay Webhook Listener)",
        "metrics_computed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }



# ── PLAN MANAGEMENT ──────────────────────────────────────────────
@router.get("/plans")
async def list_admin_plans(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.plan_manager, AdminUserRole.analyst, module='subscription_plans', action='read')),
    db: Session = Depends(get_db)
):
    """Lists all subscription plans with all versions and entitlements."""
    plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.created_at.desc()).all()
    out = []
    for p in plans:
        versions = []
        for v in p.versions:
            entitlements = {
                e.feature_key: {
                    "enabled": e.enabled,
                    "usage_limit": e.usage_limit,
                    "limit_period": e.limit_period
                } for e in v.entitlements
            }
            versions.append({
                "id": v.id,
                "version": v.version,
                "name": v.name,
                "description": v.description,
                "price_minor": v.price_minor,
                "price_formatted": f"₹{v.price_minor / 100:.2f}",
                "currency": v.currency,
                "billing_interval": v.billing_interval,
                "trial_days": v.trial_days,
                "benefits": v.benefits,
                "is_published": v.is_published,
                "available_from": v.available_from.isoformat() if v.available_from else None,
                "available_until": v.available_until.isoformat() if v.available_until else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "entitlements": entitlements
            })
        out.append({
            "id": p.id,
            "slug": p.slug,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "versions": versions
        })
    return out


@router.post("/plans")
async def create_plan(
    req: PlanCreateRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.plan_manager, module='subscription_plans', action='create')),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Creates a new subscription plan container in draft status."""
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == req.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail={"error": {"code": "SLUG_EXISTS", "message": f"Plan slug '{req.slug}' already exists."}})

    plan = SubscriptionPlan(
        id=str(uuid.uuid4()),
        slug=req.slug,
        status="draft"
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    log_admin_action(db, admin, "CREATE_PLAN", "subscription_plans", plan.id, {"slug": req.slug}, request)
    return {"id": plan.id, "slug": plan.slug, "status": plan.status}


@router.post("/plans/{plan_id}/versions")
async def create_plan_version(
    plan_id: str,
    req: VersionCreateRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.plan_manager, module='subscription_plans', action='create')),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Creates a new draft version for a plan."""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error": {"code": "PLAN_NOT_FOUND", "message": "Plan not found."}})

    # Calculate next version integer
    last_v = db.query(func.max(SubscriptionPlanVersion.version)).filter(SubscriptionPlanVersion.plan_id == plan_id).scalar() or 0
    next_v = last_v + 1

    ver = SubscriptionPlanVersion(
        id=str(uuid.uuid4()),
        plan_id=plan_id,
        version=next_v,
        name=req.name,
        description=req.description,
        price_minor=req.price_minor,
        currency=req.currency,
        billing_interval=req.billing_interval,
        trial_days=req.trial_days,
        benefits=req.benefits,
        is_published=False,
        created_by=admin.user_id
    )
    db.add(ver)

    # Add entitlements
    for feat, conf in req.entitlements.items():
        ent = PlanEntitlement(
            id=str(uuid.uuid4()),
            plan_version_id=ver.id,
            feature_key=feat,
            enabled=conf.get("enabled", True),
            usage_limit=conf.get("usage_limit"),
            limit_period=conf.get("limit_period", "monthly")
        )
        db.add(ent)

    db.commit()
    db.refresh(ver)

    log_admin_action(db, admin, "CREATE_PLAN_VERSION", "subscription_plan_versions", ver.id, {"version": next_v, "price_minor": req.price_minor}, request)
    return {"id": ver.id, "version": ver.version, "name": ver.name, "is_published": False}


@router.post("/plans/{plan_id}/versions/{version_id}/publish")
async def publish_plan_version(
    plan_id: str,
    version_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Validates and publishes a version, making it immutable and setting the plan to published."""
    ver = db.query(SubscriptionPlanVersion).filter(
        SubscriptionPlanVersion.id == version_id,
        SubscriptionPlanVersion.plan_id == plan_id
    ).first()
    if not ver:
        raise HTTPException(status_code=404, detail={"error": {"code": "VERSION_NOT_FOUND", "message": "Version not found."}})

    if ver.is_published:
        raise HTTPException(status_code=400, detail={"error": {"code": "ALREADY_PUBLISHED", "message": "This version is already published."}})

    # Validate version integrity
    if not ver.name or ver.price_minor < 0:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_VERSION", "message": "Version name and non-negative price required."}})

    ver.is_published = True
    ver.available_from = datetime.datetime.now(datetime.timezone.utc)
    
    # Also ensure parent plan is in published status
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if plan and plan.status != "published":
        plan.status = "published"

    db.commit()

    log_admin_action(db, admin, "PUBLISH_PLAN_VERSION", "subscription_plan_versions", ver.id, {"plan_id": plan_id, "version": ver.version}, request)
    return {"id": ver.id, "is_published": True, "published_at": ver.available_from.isoformat()}


@router.patch("/plans/{plan_id}/status")
async def update_plan_status(
    plan_id: str,
    req: PlanStatusUpdate,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Updates a plan's lifecycle status (draft, published, paused, archived)."""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error": {"code": "PLAN_NOT_FOUND", "message": "Plan not found."}})

    old_status = plan.status
    plan.status = req.status
    db.commit()

    log_admin_action(db, admin, "UPDATE_PLAN_STATUS", "subscription_plans", plan.id, {"from": old_status, "to": req.status}, request)
    return {"id": plan.id, "status": plan.status}


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Permanently deletes a subscription plan (including published plans) and all its versions.
    EXECUTIVE PRIVILEGE: Strictly restricted to Super Admin.
    """
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error": {"code": "PLAN_NOT_FOUND", "message": "Plan not found."}})

    # Fetch associated version IDs
    version_ids = [v.id for v in plan.versions]
    if version_ids:
        # Clean subscriptions & orders referencing these versions
        db.query(UserSubscription).filter(UserSubscription.plan_version_id.in_(version_ids)).delete(synchronize_session=False)
        db.query(PaymentOrder).filter(PaymentOrder.plan_version_id.in_(version_ids)).delete(synchronize_session=False)

    slug = plan.slug
    db.delete(plan)
    db.commit()

    log_admin_action(
        db, admin, "DELETE_PLAN", "subscription_plans", plan_id,
        {"slug": slug, "deleted_versions_count": len(version_ids)},
        request
    )

    return {"message": f"Plan '{slug}' and all associated versions successfully deleted.", "plan_id": plan_id}


@router.delete("/plans/{plan_id}/versions/{version_id}")
async def delete_plan_version(
    plan_id: str,
    version_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Permanently deletes a specific plan version (including published versions).
    EXECUTIVE PRIVILEGE: Strictly restricted to Super Admin.
    """
    ver = db.query(SubscriptionPlanVersion).filter(
        SubscriptionPlanVersion.id == version_id,
        SubscriptionPlanVersion.plan_id == plan_id
    ).first()
    if not ver:
        raise HTTPException(status_code=404, detail={"error": {"code": "VERSION_NOT_FOUND", "message": "Version not found."}})

    # Clean subscriptions & orders referencing this specific version
    db.query(UserSubscription).filter(UserSubscription.plan_version_id == version_id).delete(synchronize_session=False)
    db.query(PaymentOrder).filter(PaymentOrder.plan_version_id == version_id).delete(synchronize_session=False)

    ver_name = ver.name
    ver_num = ver.version
    db.delete(ver)

    # Check remaining versions in plan
    remaining = db.query(SubscriptionPlanVersion).filter(
        SubscriptionPlanVersion.plan_id == plan_id,
        SubscriptionPlanVersion.id != version_id
    ).all()
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if plan:
        has_published = any(r.is_published for r in remaining)
        if not has_published and plan.status == "published":
            plan.status = "draft"

    db.commit()

    log_admin_action(
        db, admin, "DELETE_PLAN_VERSION", "subscription_plan_versions", version_id,
        {"plan_id": plan_id, "version": ver_num, "name": ver_name},
        request
    )

    return {"message": f"Version '{ver_name}' (v{ver_num}) successfully deleted.", "version_id": version_id}



# ── USERS, ROLES, PERMISSIONS & AUDIT LOGS ─────────────────────────
class FarmerVerifyBody(BaseModel):
    is_verified: bool = True
    notes: Optional[str] = None


class UserSuspendBody(BaseModel):
    is_active: bool
    reason: str = Field(..., min_length=3)


@router.get("/users")
async def list_admin_users(
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    role_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = Query(100, le=500)
):
    """Lists registered users, verification status, 3-tier hierarchy level, and granular permissions."""
    query = db.query(User)
    if q:
        s = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(s), User.full_name.ilike(s), User.phone.ilike(s), User.id.ilike(s)))
    if status_filter == "active":
        query = query.filter(User.is_active == True)
    elif status_filter == "suspended":
        query = query.filter(User.is_active == False)

    users = query.order_by(User.created_at.desc()).limit(limit).all()
    admin_records = {a.user_id: a for a in db.query(AdminUser).all()}

    out = []
    for u in users:
        a_rec = admin_records.get(u.id)
        a_role = a_rec.role.value if (a_rec and a_rec.is_active) else None
        h_level = get_hierarchy_level(a_rec) if (a_rec and a_rec.is_active) else None
        perms = get_effective_permissions(a_rec) if (a_rec and a_rec.is_active) else {}
        if role_filter:
            if role_filter in ("SUPER_ADMIN_HEAD", "ADMIN", "STAFF"):
                if h_level != role_filter:
                    continue
            elif a_role != role_filter and (not u.role or u.role.value != role_filter):
                continue
        out.append({
            "id": u.id,
            "email": u.email,
            "phone": u.phone,
            "full_name": u.full_name,
            "role": u.role.value if u.role else None,
            "admin_role": a_role,
            "hierarchy_level": h_level,
            "permissions": perms,
            "is_verified": bool(u.is_verified),
            "is_active": bool(u.is_active),
            "created_at": u.created_at.isoformat() if u.created_at else None
        })
    return out


@router.post("/users/assign-role")
async def assign_admin_role(
    req: RoleAssignRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="users_roles", action="edit")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Enforces 3-Tier Role Hierarchy delegation rules:
    - Level 1 (Super Admin Head) can assign any role (super_admin, admin, staff, specialist) and any permissions.
    - Level 2 (Admin) can assign or update Level 3 (Staff) operational roles and delegate permissions ONLY within the Admin's own granted permissions.
    - Level 2 (Admin) CANNOT grant Admin or Super Admin Head roles, nor modify another Admin or the Super Admin Head.
    - Level 3 (Staff) cannot assign roles or escalate privileges.
    """
    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}})

    # Protect Head Super Admin from deactivation or demotion by anyone
    if target_user.email and target_user.email.lower() == SUPER_ADMIN_EMAIL:
        if not req.is_active or (req.role and req.role != AdminUserRole.super_admin):
            _log_unauthorized_attempt(db, target_user, admin.role.value, "Attempted to deactivate or demote Head Super Admin", request)
            raise HTTPException(status_code=400, detail={"error": {"code": "CANNOT_REVOKE_SUPER_ADMIN", "message": "Head Super Admin cannot be deactivated or demoted."}})

    caller_tier = get_hierarchy_level(admin)
    existing_target_admin = db.query(AdminUser).filter(AdminUser.user_id == req.user_id).first()

    # Prevent self-promotion by non-Super-Admin
    if caller_tier != "SUPER_ADMIN_HEAD" and req.user_id == admin.user_id:
        _log_unauthorized_attempt(db, target_user, admin.role.value, "Attempted self-role modification", request)
        raise HTTPException(status_code=403, detail={"error": {"code": "SELF_ESCALATION_FORBIDDEN", "message": "You cannot modify your own role or permissions."}})

    # If caller is Level 2 (ADMIN), enforce strict delegation boundaries
    if caller_tier != "SUPER_ADMIN_HEAD":
        if caller_tier != "ADMIN":
            _log_unauthorized_attempt(db, target_user, admin.role.value, "Staff attempted role assignment", request)
            raise HTTPException(status_code=403, detail={"error": {"code": "INSUFFICIENT_ROLE", "message": "Staff cannot assign roles or permissions."}})

        # Admin cannot modify an existing Super Admin or another Admin
        if existing_target_admin and get_hierarchy_level(existing_target_admin) in ("SUPER_ADMIN_HEAD", "ADMIN"):
            _log_unauthorized_attempt(db, target_user, admin.role.value, "Admin attempted to modify peer Admin or Super Admin Head", request)
            raise HTTPException(status_code=403, detail={"error": {"code": "ROLE_ESCALATION_FORBIDDEN", "message": "Only Head Super Admin can assign or modify Admin or Super Admin Head accounts."}})

        # Admin cannot promote anyone to super_admin or admin
        if req.role in (AdminUserRole.super_admin, AdminUserRole.admin) or req.hierarchy_level in ("SUPER_ADMIN_HEAD", "ADMIN"):
            _log_unauthorized_attempt(db, target_user, admin.role.value, f"Admin attempted to grant {req.role} / {req.hierarchy_level}", request)
            raise HTTPException(status_code=403, detail={"error": {"code": "ROLE_ESCALATION_FORBIDDEN", "message": "Admins can only assign Staff roles. Promoting to Admin or Super Admin Head requires Head Super Admin approval."}})

        # Verify delegated permissions are a strict subset of the Admin's own effective permissions
        if req.permissions:
            caller_perms = get_effective_permissions(admin)
            for mod, acts in req.permissions.items():
                allowed_for_caller = set(caller_perms.get(mod, []))
                for act in acts:
                    if act not in allowed_for_caller:
                        _log_unauthorized_attempt(db, target_user, admin.role.value, f"Admin attempted to delegate unowned permission {mod}:{act}", request)
                        raise HTTPException(
                            status_code=403,
                            detail={"error": {"code": "PERMISSION_ESCALATION_FORBIDDEN", "message": f"Cannot delegate permission '{mod}:{act}' that you do not possess."}}
                        )

    assigned_role = req.role or (existing_target_admin.role if existing_target_admin else AdminUserRole.staff)
    if assigned_role == AdminUserRole.super_admin and (not target_user.email or target_user.email.lower() != SUPER_ADMIN_EMAIL):
        # Only SUPER_ADMIN_EMAIL can hold the owner super_admin role in production/strict hierarchy unless assigned as admin
        if req.hierarchy_level == "SUPER_ADMIN_HEAD":
            _log_unauthorized_attempt(db, target_user, admin.role.value, "Attempted to create second Super Admin Head", request)
            raise HTTPException(status_code=403, detail={"error": {"code": "SINGLE_SUPER_ADMIN_HEAD", "message": f"Only {SUPER_ADMIN_EMAIL} is the designated Super Admin Head."}})

    # Determine canonical hierarchy_level
    if assigned_role == AdminUserRole.super_admin:
        target_level = "SUPER_ADMIN_HEAD"
    elif assigned_role == AdminUserRole.admin or req.hierarchy_level == "ADMIN":
        target_level = "ADMIN"
    else:
        target_level = "STAFF"

    if existing_target_admin:
        if req.role:
            existing_target_admin.role = req.role
        existing_target_admin.hierarchy_level = target_level
        if req.permissions is not None:
            existing_target_admin.permissions = req.permissions
        existing_target_admin.assigned_by = admin.user_id
        existing_target_admin.is_active = req.is_active
        admin_rec = existing_target_admin
    else:
        admin_rec = AdminUser(
            id=str(uuid.uuid4()),
            user_id=req.user_id,
            role=assigned_role,
            hierarchy_level=target_level,
            permissions=req.permissions or {},
            assigned_by=admin.user_id,
            is_active=req.is_active
        )
        db.add(admin_rec)

    db.commit()
    db.refresh(admin_rec)
    log_admin_action(
        db, admin,
        "ASSIGN_ADMIN_ROLE" if req.is_active else "REVOKE_ADMIN_ACCESS",
        "admin_users",
        admin_rec.id,
        {
            "user_id": req.user_id,
            "role": admin_rec.role.value,
            "assigned_hierarchy_level": admin_rec.hierarchy_level,
            "permissions": admin_rec.permissions,
            "is_active": admin_rec.is_active,
        },
        request
    )
    return {
        "user_id": req.user_id,
        "role": admin_rec.role.value,
        "hierarchy_level": admin_rec.hierarchy_level,
        "permissions": get_effective_permissions(admin_rec),
        "is_active": admin_rec.is_active,
        "status": "updated"
    }


@router.post("/users/{user_id}/verify-farmer")
async def verify_farmer_account(
    user_id: str,
    req: FarmerVerifyBody,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.support_agent, module="users_roles", action="edit")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Verifies or unverifies a farmer account and records an audit log."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}})
    u.is_verified = req.is_verified
    db.commit()
    log_admin_action(
        db, admin,
        "VERIFY_FARMER_ACCOUNT" if req.is_verified else "UNVERIFY_FARMER_ACCOUNT",
        "users",
        u.id,
        {"is_verified": req.is_verified, "notes": req.notes},
        request
    )
    return {"user_id": u.id, "is_verified": u.is_verified, "status": "updated"}


@router.post("/users/{user_id}/suspend")
async def suspend_or_restore_user(
    user_id: str,
    req: UserSuspendBody,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="users_roles", action="suspend")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Suspends or restores a user account with mandatory reason and audit trail."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}})
    if u.email and u.email.lower() == SUPER_ADMIN_EMAIL and not req.is_active:
        raise HTTPException(status_code=400, detail={"error": {"code": "CANNOT_SUSPEND_SUPER_ADMIN", "message": "Head Super Admin cannot be suspended."}})

    u.is_active = req.is_active
    admin_rec = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
    if admin_rec and not req.is_active:
        admin_rec.is_active = False
    db.commit()

    log_admin_action(
        db, admin,
        "RESTORE_USER_ACCOUNT" if req.is_active else "SUSPEND_USER_ACCOUNT",
        "users",
        u.id,
        {"is_active": req.is_active, "reason": req.reason},
        request
    )
    return {"user_id": u.id, "is_active": u.is_active, "reason": req.reason}


@router.get("/audit-logs")
async def get_audit_logs(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.analyst, module="audit_logs", action="read")),
    db: Session = Depends(get_db),
    action_filter: Optional[str] = None,
    actor_role: Optional[str] = None,
    target_entity: Optional[str] = None,
    limit: int = Query(100, le=500)
):
    """Lists immutable administrative audit logs. Staff cannot view audit logs unless explicitly permitted."""
    q = db.query(AdminAuditLog)
    if action_filter:
        q = q.filter(AdminAuditLog.action.ilike(f"%{action_filter.strip()}%"))
    if actor_role:
        q = q.filter(AdminAuditLog.actor_role == actor_role.strip())
    if target_entity:
        q = q.filter(AdminAuditLog.target_entity == target_entity.strip())
    logs = q.order_by(AdminAuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "actor_id": l.actor_id,
            "actor_role": l.actor_role,
            "action": l.action,
            "target_entity": l.target_entity,
            "target_id": l.target_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in logs
    ]


@router.delete("/audit-logs/{log_id}")
@router.patch("/audit-logs/{log_id}")
@router.put("/audit-logs/{log_id}")
async def block_audit_log_tampering(
    log_id: str,
    request: Request,
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Audit logs are strictly immutable; any attempt to edit or delete them is rejected and logged."""
    log_admin_action(
        db, admin,
        "AUDIT_LOG_TAMPER_ATTEMPT_BLOCKED",
        "admin_audit_logs",
        log_id,
        {"attempted_method": request.method},
        request
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "AUDIT_LOG_IMMUTABLE", "message": "Security audit logs are immutable and cannot be modified or deleted."}}
    )


# ── PAYMENTS & TRANSACTIONS ──────────────────────────────────────
class StaffAssistActivateRequest(BaseModel):
    staff_notes: str = Field(..., min_length=5)
    payment_reference: Optional[str] = None # UTR or bank reference number


class StaffAddNoteRequest(BaseModel):
    note: str = Field(..., min_length=2)


class StaffRefundRequest(BaseModel):
    reason: str = Field(..., min_length=3)


def _compute_sub_expiry(start: datetime.datetime, interval: str) -> datetime.datetime:
    if interval == "monthly":
        return start + datetime.timedelta(days=30)
    elif interval == "quarterly":
        return start + datetime.timedelta(days=90)
    elif interval == "yearly":
        return start + datetime.timedelta(days=365)
    elif interval == "lifetime":
        return start + datetime.timedelta(days=3650)
    return start + datetime.timedelta(days=30)


@router.get("/payments/orders")
async def list_payment_orders(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.payment_manager, AdminUserRole.payment_staff, AdminUserRole.support_agent, AdminUserRole.analyst, module="payment_orders", action="read")),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200)
):
    """Lists recent payment orders with customer contact information and support issue flags."""
    orders = db.query(PaymentOrder).order_by(PaymentOrder.created_at.desc()).limit(limit).all()
    out = []
    for o in orders:
        user = db.query(User).filter(User.id == o.user_id).first()
        version = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == o.plan_version_id).first()
        order_notes = o.notes or {}
        has_issue = order_notes.get("has_open_issue", False) or (o.status in ("failed", "issue_reported"))
        out.append({
            "id": o.id,
            "user_id": o.user_id,
            "user_email": user.email if user else None,
            "user_name": user.full_name if user else None,
            "user_phone": user.phone if user else None,
            "plan_version_id": o.plan_version_id,
            "plan_name": version.name if version else None,
            "amount_minor": o.amount_minor,
            "amount_formatted": f"₹{o.amount_minor / 100:.2f}",
            "currency": o.currency,
            "provider": o.provider,
            "provider_order_id": o.provider_order_id,
            "status": o.status,
            "notes": order_notes,
            "has_open_issue": has_issue,
            "created_at": o.created_at.isoformat() if o.created_at else None
        })
    return out


class PaymentDirectOverrideRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    payment_reference: Optional[str] = None


@router.post("/payments/orders/{order_id}/override-status")
async def block_unverified_payment_override(
    order_id: str,
    req: PaymentDirectOverrideRequest,
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Blocks any manual override of an unverified or failed payment order to 'paid' without verified provider transaction proof."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    if req.status.lower() == "paid":
        verified_tx = db.query(PaymentTransaction).filter(
            PaymentTransaction.order_id == order.id,
            PaymentTransaction.status == "success"
        ).first()
        if not verified_tx and not req.payment_reference:
            log_admin_action(
                db, admin,
                "UNVERIFIED_PAYMENT_OVERRIDE_BLOCKED",
                "payment_orders",
                order.id,
                {"attempted_status": req.status, "current_status": order.status},
                request
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "PAYMENT_VERIFICATION_REQUIRED", "message": "Unverified or failed payments cannot be manually marked as paid without a verified provider payment reference."}}
            )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": {"code": "DIRECT_STATUS_OVERRIDE_FORBIDDEN", "message": "Direct payment status overrides are forbidden. Use verified webhook reconciliation or authorized refund workflows."}}
    )


@router.post("/payments/orders/{order_id}/assist-activate")
async def staff_assist_activate_subscription(
    order_id: str,
    req: StaffAssistActivateRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.payment_manager, AdminUserRole.support_agent)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Resolves a payment issue (e.g. money debited from farmer bank but webhook delayed) and activates membership."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    # Update order state to paid
    order.status = "paid"
    notes = order.notes.copy() if order.notes else {}
    notes["staff_assistance"] = {
        "assisted_by_user_id": admin.user_id,
        "assisted_by_role": admin.role.value,
        "assisted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "staff_notes": req.staff_notes,
        "payment_reference": req.payment_reference,
        "resolution": "Subscription manually verified & activated by staff"
    }
    notes["has_open_issue"] = False
    order.notes = notes

    # Record verified transaction
    tx_ref = req.payment_reference or f"staff_ast_{str(uuid.uuid4())[:8]}"
    existing_tx = db.query(PaymentTransaction).filter(PaymentTransaction.provider_payment_id == tx_ref).first()
    if not existing_tx:
        tx = PaymentTransaction(
            id=str(uuid.uuid4()),
            order_id=order.id,
            user_id=order.user_id,
            amount_minor=order.amount_minor,
            currency=order.currency,
            status="success",
            provider="staff_assisted",
            provider_payment_id=tx_ref
        )
        db.add(tx)

    # Activate farmer's subscription
    version = db.query(SubscriptionPlanVersion).filter(SubscriptionPlanVersion.id == order.plan_version_id).first()
    now = datetime.datetime.now(datetime.timezone.utc)
    interval = version.billing_interval if version else "monthly"
    period_end = _compute_sub_expiry(now, interval)

    # Deactivate existing active subscriptions
    active_subs = db.query(UserSubscription).filter(
        UserSubscription.user_id == order.user_id,
        UserSubscription.status == "active"
    ).all()
    for s in active_subs:
        s.status = "superseded"

    new_sub = UserSubscription(
        id=str(uuid.uuid4()),
        user_id=order.user_id,
        plan_version_id=order.plan_version_id,
        status="active",
        current_period_start=now,
        current_period_end=period_end,
        cancel_at_period_end=False
    )
    db.add(new_sub)
    db.commit()

    log_admin_action(
        db, admin,
        "STAFF_MANUAL_PAYMENT_ACTIVATION",
        "payment_orders",
        order.id,
        {"staff_notes": req.staff_notes, "ref": req.payment_reference, "user_id": order.user_id},
        request
    )

    return {
        "success": True,
        "order_id": order.id,
        "status": order.status,
        "subscription_id": new_sub.id,
        "message": "Farmer subscription activated successfully."
    }


@router.post("/payments/orders/{order_id}/add-notes")
async def staff_add_payment_support_note(
    order_id: str,
    req: StaffAddNoteRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.payment_manager, AdminUserRole.payment_staff, AdminUserRole.support_agent, module="payment_orders", action="edit")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Staff adds an internal customer support log (e.g. phone call notes, bank refund status)."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    notes = order.notes.copy() if order.notes else {}
    staff_log = notes.get("staff_log", [])
    staff_log.append({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "staff_id": admin.user_id,
        "role": admin.role.value,
        "note": req.note
    })
    notes["staff_log"] = staff_log
    order.notes = notes
    db.commit()

    log_admin_action(
        db, admin,
        "ADD_PAYMENT_SUPPORT_NOTE",
        "payment_orders",
        order.id,
        {"note": req.note},
        request
    )

    return {"success": True, "notes": order.notes}


@router.post("/payments/orders/{order_id}/mark-refunded")
async def staff_mark_order_refunded(
    order_id: str,
    req: StaffRefundRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.payment_manager, module="payment_orders", action="approve")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Staff records that the order has been refunded to the farmer."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    order.status = "refunded"
    notes = order.notes.copy() if order.notes else {}
    notes["refund_details"] = {
        "refunded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "refunded_by": admin.user_id,
        "reason": req.reason
    }
    order.notes = notes

    # Cancel active subscription
    active_sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == order.user_id,
        UserSubscription.plan_version_id == order.plan_version_id,
        UserSubscription.status == "active"
    ).first()
    if active_sub:
        active_sub.status = "canceled"

    db.commit()

    log_admin_action(
        db, admin,
        "REFUND_PAYMENT_ORDER",
        "payment_orders",
        order.id,
        {"reason": req.reason},
        request
    )

    return {"success": True, "status": "refunded"}


@router.get("/payments/transactions")
async def list_payment_transactions(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.payment_manager, AdminUserRole.payment_staff, AdminUserRole.support_agent, AdminUserRole.analyst, module="payment_orders", action="read")),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200)
):
    """Lists verified payment transactions with settlement details."""
    txs = db.query(PaymentTransaction).order_by(PaymentTransaction.created_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "order_id": t.order_id,
            "provider": t.provider,
            "provider_payment_id": t.provider_payment_id,
            "amount_minor": t.amount_minor,
            "amount_formatted": f"₹{t.amount_minor / 100:.2f}",
            "currency": t.currency,
            "status": t.status,
            "provider_signature": t.provider_signature,
            "created_at": t.created_at.isoformat() if t.created_at else None
        } for t in txs
    ]



# ── DATA REQUESTS (CORRECTIONS, SUPPORT, PRIVACY & COMPLAINTS QUEUE) ──
class DataRequestProcessRequest(BaseModel):
    status: str = Field(..., pattern=r"^(completed|rejected|OPEN|ASSIGNED|IN_PROGRESS|RESOLVED|REJECTED)$")
    admin_notes: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None


class DataRequestCreateBody(BaseModel):
    user_id: Optional[str] = None
    request_type: str = Field("farmer_data_correction") # export, delete, farmer_data_correction, support_issue, complaint
    category: str = Field("farmer_data_correction")
    priority: str = Field("normal", pattern=r"^(low|normal|high|urgent)$")
    details: Dict[str, Any] = Field(default_factory=dict)


class DataRequestWorkflowUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(OPEN|ASSIGNED|IN_PROGRESS|RESOLVED|REJECTED|pending|processing|completed|rejected)$")
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    admin_notes: Optional[str] = None


@router.get("/data-requests")
async def list_data_requests(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.support_agent, AdminUserRole.analyst, module="data_requests", action="read")),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """Lists farmer data corrections, support issues, privacy export/delete requests, and complaints."""
    q = db.query(DataRequest)
    if status_filter:
        q = q.filter(DataRequest.status == status_filter)
    requests = q.order_by(DataRequest.created_at.desc()).limit(limit).all()
    out = []
    for r in requests:
        user = db.query(User).filter(User.id == r.user_id).first()
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "user_email": user.email if user else None,
            "user_name": user.full_name if user else None,
            "request_type": r.request_type,
            "category": getattr(r, "category", None) or r.request_type,
            "priority": getattr(r, "priority", None) or "normal",
            "assigned_to": getattr(r, "assigned_to", None),
            "status": r.status,
            "details": r.details or {},
            "admin_notes": r.admin_notes,
            "processed_by": r.processed_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None
        })
    return out


@router.post("/data-requests")
async def create_admin_data_request(
    req: DataRequestCreateBody,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.support_agent, module="data_requests", action="create")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Creates a new customer data correction, support task, or privacy request in OPEN state."""
    target_uid = req.user_id or admin.user_id
    dr = DataRequest(
        id=str(uuid.uuid4()),
        user_id=target_uid,
        request_type=req.request_type,
        category=req.category,
        priority=req.priority,
        status="OPEN",
        details=req.details or {},
    )
    db.add(dr)
    db.commit()
    db.refresh(dr)
    log_admin_action(db, admin, "CREATE_DATA_REQUEST", "data_requests", dr.id, {"type": req.request_type, "priority": req.priority}, request)
    return {"id": dr.id, "status": dr.status, "request_type": dr.request_type, "priority": dr.priority}


@router.patch("/data-requests/{request_id}/workflow")
async def update_data_request_workflow(
    request_id: str,
    req: DataRequestWorkflowUpdate,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.support_agent, module="data_requests", action="edit")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Transitions a data request across OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED / REJECTED."""
    dr = db.query(DataRequest).filter(DataRequest.id == request_id).first()
    if not dr:
        raise HTTPException(status_code=404, detail={"error": {"code": "REQUEST_NOT_FOUND", "message": "Data request not found."}})

    old_status = dr.status
    dr.status = req.status
    if req.assigned_to is not None:
        dr.assigned_to = req.assigned_to
    if req.priority is not None:
        dr.priority = req.priority
    if req.admin_notes is not None:
        dr.admin_notes = req.admin_notes
    if req.status in ("RESOLVED", "REJECTED", "completed", "rejected"):
        dr.processed_by = admin.user_id
        dr.processed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(
        db, admin,
        f"WORKFLOW_DATA_REQUEST_{req.status.upper()}",
        "data_requests",
        dr.id,
        {"from": old_status, "to": req.status, "assigned_to": dr.assigned_to, "notes": req.admin_notes},
        request
    )
    return {
        "id": dr.id,
        "status": dr.status,
        "assigned_to": dr.assigned_to,
        "priority": dr.priority,
        "admin_notes": dr.admin_notes,
        "processed_at": dr.processed_at.isoformat() if dr.processed_at else None,
    }


@router.post("/data-requests/{request_id}/process")
async def process_data_request(
    request_id: str,
    req: DataRequestProcessRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.support_agent, module="data_requests", action="approve")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Processes a privacy or operational data request (fulfillment or rejection)."""
    dr = db.query(DataRequest).filter(DataRequest.id == request_id).first()
    if not dr:
        raise HTTPException(status_code=404, detail={"error": {"code": "REQUEST_NOT_FOUND", "message": "Data request not found."}})

    dr.status = req.status
    dr.admin_notes = req.admin_notes
    if req.assigned_to is not None:
        dr.assigned_to = req.assigned_to
    if req.priority is not None:
        dr.priority = req.priority
    dr.processed_by = admin.user_id
    dr.processed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(
        db, admin,
        f"PROCESS_DATA_REQUEST_{req.status.upper()}",
        "data_requests",
        dr.id,
        {"request_type": dr.request_type, "status": req.status, "notes": req.admin_notes},
        request
    )
    return {"id": dr.id, "status": dr.status, "processed_at": dr.processed_at.isoformat()}


# ── FARMER REGISTRY EXCEL & CSV EXPORTS ──────────────────────────

@router.get("/export/farmers-excel")
async def export_farmers_excel(
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Generates and streams a styled Microsoft Excel workbook containing all registered farmers and agricultural data."""
    data = fetch_farmer_export_data(db)
    excel_bytes = generate_farmers_excel_bytes(data)
    filename = f"Agro_AI_Farmers_Registry_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/export/farmers-csv")
async def export_farmers_csv(
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Generates and streams a standard UTF-8 BOM CSV containing all registered farmers for direct Excel opening."""
    data = fetch_farmer_export_data(db)
    csv_bytes = generate_farmers_csv_bytes(data)
    filename = f"Agro_AI_Farmers_Registry_{datetime.date.today().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/export/summary")
async def get_export_summary(
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Returns metadata about the registered farmers spreadsheet stored on disk, ensuring fresh live sync."""
    data = fetch_farmer_export_data(db)
    # Always sync physical files on disk with latest live data
    generate_farmers_excel_bytes(data)
    generate_farmers_csv_bytes(data)
    xlsx_path = os.path.join(EXPORT_DIR, "farmers_registry.xlsx")
    csv_path = os.path.join(EXPORT_DIR, "farmers_registry.csv")
    file_exists = os.path.exists(xlsx_path)
    file_size_kb = round(os.path.getsize(xlsx_path) / 1024, 2) if file_exists else 0.0

    return {
        "total_farmers": len(data),
        "file_persisted_on_disk": file_exists,
        "excel_file_path": xlsx_path,
        "csv_file_path": csv_path,
        "file_size_kb": file_size_kb,
        "last_updated": datetime.datetime.fromtimestamp(os.path.getmtime(xlsx_path), datetime.timezone.utc).isoformat() if file_exists else None
    }



# ── BROADCAST POSTS & OFFERS (DRAFT -> SUBMITTED -> APPROVED/PUBLISHED -> ARCHIVED) ──

class BroadcastCreateRequest(BaseModel):
    item_type: str = Field("post", pattern=r"^(post|offer|advisory)$")
    title: str = Field(..., min_length=3, max_length=200)
    content: str = Field(..., min_length=5)
    language: str = Field("en")
    category: str = Field("general")
    target_region: Optional[str] = None
    discount_percent: Optional[float] = None
    discount_code: Optional[str] = None
    target_plan_slug: Optional[str] = None
    banner_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    valid_from: Optional[datetime.datetime] = None
    valid_until: Optional[datetime.datetime] = None
    submit_for_approval: bool = False


class BroadcastUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None
    category: Optional[str] = None
    target_region: Optional[str] = None
    discount_percent: Optional[float] = None
    discount_code: Optional[str] = None
    target_plan_slug: Optional[str] = None
    banner_url: Optional[str] = None
    tags: Optional[List[str]] = None
    valid_from: Optional[datetime.datetime] = None
    valid_until: Optional[datetime.datetime] = None


class BroadcastRejectRequest(BaseModel):
    rejection_notes: str = Field(..., min_length=2)


@router.get("/broadcasts")
async def list_broadcast_items(
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Lists all marketing posts, advisory updates, and promotional offers with approval states."""
    items = db.query(BroadcastItem).order_by(BroadcastItem.created_at.desc()).all()
    out = []
    for it in items:
        author = db.query(User).filter(User.id == it.created_by).first() if it.created_by else None
        approver = db.query(User).filter(User.id == it.approved_by).first() if it.approved_by else None
        out.append({
            "id": it.id,
            "item_type": it.item_type.value,
            "title": it.title,
            "content": it.content,
            "language": getattr(it, "language", "en") or "en",
            "category": getattr(it, "category", "general") or "general",
            "target_region": getattr(it, "target_region", None),
            "discount_percent": it.discount_percent,
            "discount_code": it.discount_code,
            "target_plan_slug": it.target_plan_slug,
            "banner_url": it.banner_url,
            "tags": it.tags or [],
            "status": it.status.value,
            "created_by": it.created_by,
            "author_name": author.full_name if author else (author.email if author else "Unknown"),
            "author_email": author.email if author else None,
            "submitted_at": it.submitted_at.isoformat() if it.submitted_at else None,
            "approved_by": it.approved_by,
            "approver_name": approver.full_name if approver else None,
            "approved_at": it.approved_at.isoformat() if it.approved_at else None,
            "super_admin_notes": it.super_admin_notes,
            "valid_from": it.valid_from.isoformat() if it.valid_from else None,
            "valid_until": it.valid_until.isoformat() if it.valid_until else None,
            "created_at": it.created_at.isoformat() if it.created_at else None
        })
    return out


@router.post("/broadcasts")
async def create_broadcast_item(
    req: BroadcastCreateRequest,
    admin: AdminUser = Depends(require_admin(module="posts_offers", action="create")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Staff/Admins can create draft posts/offers or submit for approval. Super Admin can publish directly."""
    is_sa = (admin.role == AdminUserRole.super_admin)
    initial_status = BroadcastStatus.draft
    if req.submit_for_approval:
        initial_status = BroadcastStatus.pending_approval

    if is_sa and req.submit_for_approval:
        initial_status = BroadcastStatus.approved

    now = datetime.datetime.now(datetime.timezone.utc)
    item = BroadcastItem(
        id=str(uuid.uuid4()),
        item_type=BroadcastType(req.item_type),
        title=req.title,
        content=req.content,
        language=req.language or "en",
        category=req.category or "general",
        target_region=req.target_region,
        discount_percent=req.discount_percent,
        discount_code=req.discount_code,
        target_plan_slug=req.target_plan_slug,
        banner_url=req.banner_url,
        tags=req.tags,
        status=initial_status,
        created_by=admin.user_id,
        submitted_at=now if (initial_status in (BroadcastStatus.pending_approval, BroadcastStatus.approved)) else None,
        approved_by=admin.user_id if initial_status == BroadcastStatus.approved else None,
        approved_at=now if initial_status == BroadcastStatus.approved else None,
        valid_from=req.valid_from or now,
        valid_until=req.valid_until
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    log_admin_action(
        db, admin,
        "CREATE_BROADCAST_ITEM",
        "broadcast_items",
        item.id,
        {"type": req.item_type, "title": req.title, "status": item.status.value, "language": item.language},
        request
    )
    return {
        "id": item.id,
        "title": item.title,
        "item_type": item.item_type.value,
        "status": item.status.value,
        "message": "Post created and submitted for approval." if item.status == BroadcastStatus.pending_approval else ("Post published directly by Super Admin." if item.status == BroadcastStatus.approved else "Post saved as draft.")
    }


@router.patch("/broadcasts/{broadcast_id}")
async def update_broadcast_item(
    broadcast_id: str,
    req: BroadcastUpdateRequest,
    admin: AdminUser = Depends(require_admin(module="posts_offers", action="edit")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Updates a draft or rejected post/offer."""
    item = db.query(BroadcastItem).filter(BroadcastItem.id == broadcast_id).first()
    if not item:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Post or offer not found."}})

    if req.title is not None:
        item.title = req.title
    if req.content is not None:
        item.content = req.content
    if req.language is not None:
        item.language = req.language
    if req.category is not None:
        item.category = req.category
    if req.target_region is not None:
        item.target_region = req.target_region
    if req.discount_percent is not None:
        item.discount_percent = req.discount_percent
    if req.discount_code is not None:
        item.discount_code = req.discount_code
    if req.tags is not None:
        item.tags = req.tags
    if req.valid_from is not None:
        item.valid_from = req.valid_from
    if req.valid_until is not None:
        item.valid_until = req.valid_until
    db.commit()

    log_admin_action(db, admin, "UPDATE_BROADCAST_ITEM", "broadcast_items", item.id, {"title": item.title}, request)
    return {"id": item.id, "title": item.title, "status": item.status.value}


@router.post("/broadcasts/{broadcast_id}/submit")
async def submit_broadcast_for_approval(
    broadcast_id: str,
    admin: AdminUser = Depends(require_admin(module="posts_offers", action="submit")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Submits a draft post or offer for Admin / Super Admin approval."""
    item = db.query(BroadcastItem).filter(BroadcastItem.id == broadcast_id).first()
    if not item:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Post or offer not found."}})

    if item.status == BroadcastStatus.approved:
        raise HTTPException(status_code=400, detail={"error": {"code": "ALREADY_APPROVED", "message": "This post is already approved and live."}})

    item.status = BroadcastStatus.pending_approval
    item.submitted_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(db, admin, "SUBMIT_BROADCAST_FOR_APPROVAL", "broadcast_items", item.id, {"title": item.title}, request)
    return {"id": item.id, "status": item.status.value, "message": f"Submitted '{item.title}' for Super Admin approval."}


@router.post("/broadcasts/{broadcast_id}/approve")
async def approve_broadcast_item(
    broadcast_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="posts_offers", action="approve")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Super Admin Head or authorized Level 2 Admin approves a post or promotional offer to make it live for farmers. Self-approval by non-Super-Admin is forbidden."""
    item = db.query(BroadcastItem).filter(BroadcastItem.id == broadcast_id).first()
    if not item:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Post or offer not found."}})

    if admin.role != AdminUserRole.super_admin and item.created_by == admin.user_id:
        log_admin_action(db, admin, "SELF_APPROVAL_BLOCKED", "broadcast_items", item.id, {"title": item.title}, request)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "SELF_APPROVAL_FORBIDDEN", "message": "You cannot self-approve a post or offer that you created."}}
        )

    item.status = BroadcastStatus.approved
    item.approved_by = admin.user_id
    item.approved_at = datetime.datetime.now(datetime.timezone.utc)
    item.super_admin_notes = "Approved by Head Super Admin Vivek Shastry" if admin.role == AdminUserRole.super_admin else f"Approved by Admin ({admin.user_id})"
    db.commit()

    log_admin_action(db, admin, "APPROVE_BROADCAST_ITEM", "broadcast_items", item.id, {"title": item.title, "type": item.item_type.value}, request)
    return {"id": item.id, "status": item.status.value, "message": f"Successfully approved '{item.title}'. It is now live to all farmers."}


@router.post("/broadcasts/{broadcast_id}/reject")
async def reject_broadcast_item(
    broadcast_id: str,
    req: BroadcastRejectRequest,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="posts_offers", action="approve")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Super Admin Head or Level 2 Admin rejects a post or offer with notes explaining requested changes."""
    item = db.query(BroadcastItem).filter(BroadcastItem.id == broadcast_id).first()
    if not item:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Post or offer not found."}})

    item.status = BroadcastStatus.rejected
    item.super_admin_notes = req.rejection_notes
    item.approved_by = admin.user_id
    item.approved_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(db, admin, "REJECT_BROADCAST_ITEM", "broadcast_items", item.id, {"title": item.title, "notes": req.rejection_notes}, request)
    return {"id": item.id, "status": item.status.value, "message": f"Rejected '{item.title}'."}


@router.post("/broadcasts/{broadcast_id}/archive")
async def archive_broadcast_item(
    broadcast_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="posts_offers", action="publish")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Archives a published or expired post/offer so it is removed from the live farmer feed."""
    item = db.query(BroadcastItem).filter(BroadcastItem.id == broadcast_id).first()
    if not item:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Post or offer not found."}})

    item.status = BroadcastStatus.archived
    db.commit()
    log_admin_action(db, admin, "ARCHIVE_BROADCAST_ITEM", "broadcast_items", item.id, {"title": item.title}, request)
    return {"id": item.id, "status": item.status.value, "message": f"Archived '{item.title}'."}


@router.delete("/broadcasts/{broadcast_id}")
async def delete_broadcast_item(
    broadcast_id: str,
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Deletes a broadcast item."""
    item = db.query(BroadcastItem).filter(BroadcastItem.id == broadcast_id).first()
    if not item:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Post or offer not found."}})

    if admin.role != AdminUserRole.super_admin and item.created_by != admin.user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "You can only delete your own draft posts."}})

    db.delete(item)
    db.commit()
    log_admin_action(db, admin, "DELETE_BROADCAST_ITEM", "broadcast_items", broadcast_id, {}, request)
    return {"status": "deleted", "id": broadcast_id}


# ── EXCEL DATA REGISTRY: IMPORT, VALIDATION, PREVIEW, APPROVAL & ROLLBACK ──

MAX_IMPORT_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMPORT_DATASETS = {"mandi_prices", "mandi_markets", "camp_registrations", "advisories"}
RESTRICTED_IMPORT_DATASETS = {"payments", "payment_orders", "users_roles", "permissions", "subscriptions"}


class ExcelImportPayload(BaseModel):
    filename: str = Field(..., min_length=3, max_length=255)
    target_dataset: str = Field("mandi_prices")
    column_mapping: Optional[Dict[str, str]] = None
    csv_content: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None


class ExcelJobDecisionBody(BaseModel):
    review_notes: Optional[str] = None


def _validate_and_parse_excel_rows(
    db: Session,
    target_dataset: str,
    raw_rows: List[Dict[str, Any]],
    column_mapping: Optional[Dict[str, str]] = None
):
    """Validates each row against dataset schema rules, detects duplicates, and separates valid preview rows from error rows."""
    mapping = column_mapping or {}
    valid_rows = []
    error_rows = []
    duplicate_count = 0
    seen_keys = set()

    for idx, raw in enumerate(raw_rows, start=1):
        # Apply column mapping if provided
        row = {}
        for k, v in (raw or {}).items():
            clean_k = str(k).strip()
            mapped_k = mapping.get(clean_k, clean_k).lower().strip().replace(" ", "_")
            row[mapped_k] = v.strip() if isinstance(v, str) else v

        if target_dataset == "mandi_prices":
            commodity = str(row.get("commodity") or "").strip()
            market_name = str(row.get("market_name") or row.get("market") or "").strip()
            state = str(row.get("state") or "").strip()
            district = str(row.get("district") or "").strip()
            variety = str(row.get("variety") or "FAQ").strip()
            unit = str(row.get("unit") or "quintal").strip()

            if not commodity or not market_name or not state or not district:
                error_rows.append({
                    "row": idx,
                    "field": "commodity/market_name/state/district",
                    "error": "Missing required fields: commodity, market_name, state, and district are mandatory.",
                    "raw": row,
                })
                continue

            try:
                modal_price = float(row.get("modal_price"))
                min_price = float(row.get("min_price", modal_price))
                max_price = float(row.get("max_price", modal_price))
            except (TypeError, ValueError):
                error_rows.append({
                    "row": idx,
                    "field": "modal_price/min_price/max_price",
                    "error": "Price values must be valid numbers.",
                    "raw": row,
                })
                continue

            if modal_price <= 0 or min_price <= 0 or max_price <= 0:
                error_rows.append({
                    "row": idx,
                    "field": "modal_price",
                    "error": "Prices must be greater than zero.",
                    "raw": row,
                })
                continue

            if min_price > modal_price or modal_price > max_price:
                error_rows.append({
                    "row": idx,
                    "field": "min_price/modal_price/max_price",
                    "error": f"Invalid price range: min_price ({min_price}) <= modal_price ({modal_price}) <= max_price ({max_price}) violated.",
                    "raw": row,
                })
                continue

            dedup_key = (state.lower(), district.lower(), market_name.lower(), commodity.lower(), variety.lower())
            if dedup_key in seen_keys:
                duplicate_count += 1
                error_rows.append({
                    "row": idx,
                    "field": "duplicate",
                    "error": f"Duplicate row in upload for {commodity} at {market_name} ({district}).",
                    "raw": row,
                })
                continue
            seen_keys.add(dedup_key)

            valid_rows.append({
                "row": idx,
                "commodity": commodity,
                "variety": variety,
                "market_name": market_name,
                "state": state,
                "district": district,
                "min_price": min_price,
                "max_price": max_price,
                "modal_price": modal_price,
                "unit": unit,
            })

        elif target_dataset == "mandi_markets":
            market_name = str(row.get("market_name") or row.get("market") or "").strip()
            district = str(row.get("district") or "").strip()
            state = str(row.get("state") or "").strip()
            market_type = str(row.get("market_type") or "Principal Yard").strip()

            if not market_name or not district or not state:
                error_rows.append({
                    "row": idx,
                    "field": "market_name/district/state",
                    "error": "Missing required fields: market_name, district, and state are mandatory.",
                    "raw": row,
                })
                continue

            dedup_key = (state.lower(), district.lower(), market_name.lower())
            existing_mkt = db.query(MandiMarket).filter(
                func.lower(MandiMarket.state) == state.lower(),
                func.lower(MandiMarket.district) == district.lower(),
                func.lower(MandiMarket.market_name) == market_name.lower(),
            ).first()
            if dedup_key in seen_keys or existing_mkt:
                duplicate_count += 1
                error_rows.append({
                    "row": idx,
                    "field": "duplicate",
                    "error": f"Duplicate market '{market_name}' in {district}, {state}.",
                    "raw": row,
                })
                continue
            seen_keys.add(dedup_key)

            valid_rows.append({
                "row": idx,
                "market_name": market_name,
                "district": district,
                "state": state,
                "market_type": market_type,
            })

        elif target_dataset == "camp_registrations":
            farmer_name = str(row.get("farmer_name") or row.get("full_name") or "").strip()
            phone = str(row.get("phone") or "").strip()
            village = str(row.get("village") or "").strip()
            district = str(row.get("district") or "").strip()
            state = str(row.get("state") or "Karnataka").strip()

            if not farmer_name or not phone or len(phone) < 10 or not village or not district:
                error_rows.append({
                    "row": idx,
                    "field": "farmer_name/phone/village/district",
                    "error": "farmer_name, valid 10-digit phone, village, and district are required.",
                    "raw": row,
                })
                continue

            dedup_key = (phone, village.lower())
            if dedup_key in seen_keys:
                duplicate_count += 1
                error_rows.append({
                    "row": idx,
                    "field": "duplicate",
                    "error": f"Duplicate camp registration for phone {phone} in {village}.",
                    "raw": row,
                })
                continue
            seen_keys.add(dedup_key)

            valid_rows.append({
                "row": idx,
                "farmer_name": farmer_name,
                "phone": phone,
                "village": village,
                "district": district,
                "state": state,
            })

        elif target_dataset == "advisories":
            title = str(row.get("title") or "").strip()
            content = str(row.get("content") or "").strip()
            language = str(row.get("language") or "en").strip()
            if len(title) < 3 or len(content) < 5:
                error_rows.append({
                    "row": idx,
                    "field": "title/content",
                    "error": "title (min 3 chars) and content (min 5 chars) are required.",
                    "raw": row,
                })
                continue
            dedup_key = (title.lower(), language.lower())
            if dedup_key in seen_keys:
                duplicate_count += 1
                error_rows.append({
                    "row": idx,
                    "field": "duplicate",
                    "error": f"Duplicate advisory title '{title}'.",
                    "raw": row,
                })
                continue
            seen_keys.add(dedup_key)
            valid_rows.append({
                "row": idx,
                "title": title,
                "content": content,
                "language": language,
            })

    return valid_rows, error_rows, duplicate_count


@router.post("/excel-registry/upload")
async def upload_excel_registry_job(
    req: ExcelImportPayload,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, AdminUserRole.staff, AdminUserRole.support_agent, AdminUserRole.content_manager, module="excel_registry", action="create")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Validates, maps columns, detects duplicates, and creates an ExcelImportJob in PENDING_REVIEW status.
    Never publishes unvalidated rows directly and never allows importing restricted datasets (payments, roles).
    """
    fname = req.filename.strip()
    ext = os.path.splitext(fname)[1].lower().lstrip(".")
    if ext not in ("csv", "xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_FILE_TYPE", "message": f"Unsupported file type '.{ext}'. Only .csv and .xlsx spreadsheets are permitted."}}
        )

    target = req.target_dataset.strip().lower()
    if target in RESTRICTED_IMPORT_DATASETS:
        log_admin_action(db, admin, "RESTRICTED_EXCEL_IMPORT_BLOCKED", "excel_import_jobs", fname, {"target_dataset": target}, request)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "RESTRICTED_IMPORT_TARGET", "message": f"Importing into '{target}' via Excel Registry is strictly prohibited to protect payment and permission integrity."}}
        )
    if target not in ALLOWED_IMPORT_DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "UNSUPPORTED_DATASET", "message": f"Allowed target datasets: {sorted(ALLOWED_IMPORT_DATASETS)}"}}
        )

    raw_rows: List[Dict[str, Any]] = []
    size_bytes = 0
    if req.csv_content is not None:
        size_bytes = len(req.csv_content.encode("utf-8"))
        if size_bytes > MAX_IMPORT_FILE_BYTES:
            raise HTTPException(status_code=400, detail={"error": {"code": "FILE_TOO_LARGE", "message": "Spreadsheet exceeds 10 MB limit."}})
        reader = csv.DictReader(io.StringIO(req.csv_content.strip()))
        raw_rows = [dict(r) for r in reader]
    elif req.rows is not None:
        size_bytes = len(json.dumps(req.rows).encode("utf-8"))
        if size_bytes > MAX_IMPORT_FILE_BYTES:
            raise HTTPException(status_code=400, detail={"error": {"code": "FILE_TOO_LARGE", "message": "Spreadsheet exceeds 10 MB limit."}})
        raw_rows = req.rows
    else:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_UPLOAD", "message": "Provide either csv_content or rows."}})

    if len(raw_rows) == 0:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_SPREADSHEET", "message": "Uploaded spreadsheet contains 0 data rows."}})

    valid_rows, error_rows, duplicate_count = _validate_and_parse_excel_rows(
        db, target, raw_rows, req.column_mapping
    )

    job = ExcelImportJob(
        id=str(uuid.uuid4()),
        filename=fname,
        file_type=ext,
        file_size_bytes=size_bytes,
        target_dataset=target,
        column_mapping=req.column_mapping or {},
        total_rows=len(raw_rows),
        valid_rows_count=len(valid_rows),
        invalid_rows_count=len(error_rows),
        duplicate_rows_count=duplicate_count,
        preview_rows=valid_rows,
        error_rows=error_rows,
        status="PENDING_REVIEW",
        uploaded_by=admin.user_id,
        uploaded_by_role=admin.role.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    log_admin_action(
        db, admin,
        "UPLOAD_EXCEL_IMPORT_JOB",
        "excel_import_jobs",
        job.id,
        {
            "filename": fname,
            "target_dataset": target,
            "total_rows": job.total_rows,
            "valid_rows": job.valid_rows_count,
            "invalid_rows": job.invalid_rows_count,
            "duplicates": job.duplicate_rows_count,
        },
        request
    )

    return {
        "id": job.id,
        "filename": job.filename,
        "file_type": job.file_type,
        "target_dataset": job.target_dataset,
        "status": job.status,
        "total_rows": job.total_rows,
        "valid_rows_count": job.valid_rows_count,
        "invalid_rows_count": job.invalid_rows_count,
        "duplicate_rows_count": job.duplicate_rows_count,
        "preview_rows": job.preview_rows[:50],
        "error_rows": job.error_rows[:50],
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/excel-registry/jobs")
async def list_excel_import_jobs(
    admin: AdminUser = Depends(require_admin(module="excel_registry", action="read")),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """Lists all spreadsheet import jobs with validation counts and approval status."""
    q = db.query(ExcelImportJob)
    if status_filter:
        q = q.filter(ExcelImportJob.status == status_filter)
    jobs = q.order_by(ExcelImportJob.created_at.desc()).limit(limit).all()
    return [
        {
            "id": j.id,
            "filename": j.filename,
            "file_type": j.file_type,
            "file_size_bytes": j.file_size_bytes,
            "target_dataset": j.target_dataset,
            "total_rows": j.total_rows,
            "valid_rows_count": j.valid_rows_count,
            "invalid_rows_count": j.invalid_rows_count,
            "duplicate_rows_count": j.duplicate_rows_count,
            "status": j.status,
            "uploaded_by": j.uploaded_by,
            "uploaded_by_role": j.uploaded_by_role,
            "reviewed_by": j.reviewed_by,
            "reviewed_at": j.reviewed_at.isoformat() if j.reviewed_at else None,
            "published_by": j.published_by,
            "published_at": j.published_at.isoformat() if j.published_at else None,
            "review_notes": j.review_notes,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.get("/excel-registry/jobs/{job_id}")
async def get_excel_import_job_detail(
    job_id: str,
    admin: AdminUser = Depends(require_admin(module="excel_registry", action="read")),
    db: Session = Depends(get_db)
):
    """Returns full validation preview and row-level errors for a spreadsheet import job."""
    j = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Excel import job not found."}})
    return {
        "id": j.id,
        "filename": j.filename,
        "file_type": j.file_type,
        "file_size_bytes": j.file_size_bytes,
        "target_dataset": j.target_dataset,
        "column_mapping": j.column_mapping or {},
        "total_rows": j.total_rows,
        "valid_rows_count": j.valid_rows_count,
        "invalid_rows_count": j.invalid_rows_count,
        "duplicate_rows_count": j.duplicate_rows_count,
        "preview_rows": j.preview_rows or [],
        "error_rows": j.error_rows or [],
        "status": j.status,
        "uploaded_by": j.uploaded_by,
        "uploaded_by_role": j.uploaded_by_role,
        "reviewed_by": j.reviewed_by,
        "reviewed_at": j.reviewed_at.isoformat() if j.reviewed_at else None,
        "published_by": j.published_by,
        "published_at": j.published_at.isoformat() if j.published_at else None,
        "review_notes": j.review_notes,
        "published_record_ids": j.published_record_ids or [],
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


@router.get("/excel-registry/jobs/{job_id}/errors-csv")
async def download_excel_job_error_report(
    job_id: str,
    admin: AdminUser = Depends(require_admin(module="excel_registry", action="read")),
    db: Session = Depends(get_db)
):
    """Downloads a CSV report of invalid rows with row numbers, fields, and error reasons."""
    j = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Excel import job not found."}})

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Row Number", "Field", "Error Reason", "Raw Data"])
    for err in (j.error_rows or []):
        writer.writerow([err.get("row"), err.get("field"), err.get("error"), json.dumps(err.get("raw", {}))])

    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="import_errors_{j.id[:8]}.csv"'}
    )


@router.post("/excel-registry/jobs/{job_id}/approve")
async def approve_excel_import_job(
    job_id: str,
    req: ExcelJobDecisionBody = None,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="excel_registry", action="approve")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Admin or Super Admin Head approves a validated spreadsheet import job. Staff cannot approve or self-approve."""
    j = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Excel import job not found."}})

    if admin.role != AdminUserRole.super_admin and j.uploaded_by == admin.user_id:
        log_admin_action(db, admin, "SELF_APPROVAL_BLOCKED", "excel_import_jobs", j.id, {"filename": j.filename}, request)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "SELF_APPROVAL_FORBIDDEN", "message": "You cannot self-approve a spreadsheet import job that you uploaded."}}
        )

    if j.valid_rows_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_VALID_ROWS", "message": "Cannot approve an import job with 0 valid rows."}}
        )

    j.status = "APPROVED"
    j.reviewed_by = admin.user_id
    j.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    if req and req.review_notes:
        j.review_notes = req.review_notes
    db.commit()

    log_admin_action(db, admin, "APPROVE_EXCEL_IMPORT_JOB", "excel_import_jobs", j.id, {"filename": j.filename, "valid_rows": j.valid_rows_count}, request)
    return {"id": j.id, "status": j.status, "reviewed_by": j.reviewed_by, "reviewed_at": j.reviewed_at.isoformat()}


@router.post("/excel-registry/jobs/{job_id}/publish")
async def publish_excel_import_job(
    job_id: str,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="excel_registry", action="publish")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Publishes validated rows from an APPROVED import job into live database tables."""
    j = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Excel import job not found."}})

    if j.status == "PUBLISHED":
        raise HTTPException(status_code=400, detail={"error": {"code": "ALREADY_PUBLISHED", "message": "This import job has already been published."}})

    if j.status not in ("APPROVED", "PENDING_REVIEW"):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_JOB_STATUS", "message": f"Cannot publish job from status '{j.status}'."}})

    if admin.role != AdminUserRole.super_admin:
        if j.status != "APPROVED":
            raise HTTPException(status_code=400, detail={"error": {"code": "APPROVAL_REQUIRED_BEFORE_PUBLISH", "message": "Import job must be in APPROVED status before publishing."}})
        if j.uploaded_by == admin.user_id and j.reviewed_by == admin.user_id:
            raise HTTPException(status_code=403, detail={"error": {"code": "SELF_APPROVAL_FORBIDDEN", "message": "Self-approval and publication of own upload is forbidden."}})

    if j.valid_rows_count == 0 or not j.preview_rows:
        raise HTTPException(status_code=400, detail={"error": {"code": "NO_VALID_ROWS", "message": "No valid rows to publish."}})

    now = datetime.datetime.now(datetime.timezone.utc)
    created_ids: List[str] = []

    if j.target_dataset == "mandi_prices":
        for r in j.preview_rows:
            rec_id = str(uuid.uuid4())
            mp = MarketPrice(
                id=rec_id,
                commodity=r["commodity"],
                variety=r.get("variety", "FAQ"),
                market_name=r["market_name"],
                state=r["state"],
                district=r["district"],
                min_price=float(r["min_price"]),
                max_price=float(r["max_price"]),
                modal_price=float(r["modal_price"]),
                unit=r.get("unit", "quintal"),
                price_date=now,
                data_source=f"Verified Excel Registry Import ({j.filename})"
            )
            db.add(mp)
            created_ids.append(rec_id)
    elif j.target_dataset == "mandi_markets":
        for r in j.preview_rows:
            existing = db.query(MandiMarket).filter(
                func.lower(MandiMarket.state) == r["state"].lower(),
                func.lower(MandiMarket.district) == r["district"].lower(),
                func.lower(MandiMarket.market_name) == r["market_name"].lower(),
            ).first()
            if existing:
                continue
            rec_id = str(uuid.uuid4())
            mm = MandiMarket(
                id=rec_id,
                market_name=r["market_name"],
                district=r["district"],
                state=r["state"],
                market_type=r.get("market_type", "Principal Yard"),
                data_source=f"Verified Excel Registry Import ({j.filename})",
                is_active=True
            )
            db.add(mm)
            created_ids.append(rec_id)
    elif j.target_dataset == "advisories":
        for r in j.preview_rows:
            rec_id = str(uuid.uuid4())
            bi = BroadcastItem(
                id=rec_id,
                item_type=BroadcastType.advisory,
                title=r["title"],
                content=r["content"],
                language=r.get("language", "en"),
                category="farming_advisory",
                status=BroadcastStatus.approved,
                created_by=j.uploaded_by or admin.user_id,
                submitted_at=now,
                approved_by=admin.user_id,
                approved_at=now,
                valid_from=now
            )
            db.add(bi)
            created_ids.append(rec_id)
    elif j.target_dataset == "camp_registrations":
        for r in j.preview_rows:
            rec_id = str(uuid.uuid4())
            dr = DataRequest(
                id=rec_id,
                user_id=admin.user_id,
                request_type="camp_registration",
                category="camp_registration",
                status="RESOLVED",
                details=r,
                processed_by=admin.user_id,
                processed_at=now,
                admin_notes=f"Imported from {j.filename}"
            )
            db.add(dr)
            created_ids.append(rec_id)

    j.status = "PUBLISHED"
    if not j.reviewed_by:
        j.reviewed_by = admin.user_id
        j.reviewed_at = now
    j.published_by = admin.user_id
    j.published_at = now
    j.published_record_ids = created_ids
    db.commit()

    log_admin_action(
        db, admin,
        "PUBLISH_EXCEL_IMPORT_JOB",
        "excel_import_jobs",
        j.id,
        {"filename": j.filename, "target_dataset": j.target_dataset, "published_count": len(created_ids)},
        request
    )
    return {
        "id": j.id,
        "status": j.status,
        "published_records_count": len(created_ids),
        "published_at": j.published_at.isoformat(),
    }


@router.post("/excel-registry/jobs/{job_id}/reject")
async def reject_excel_import_job(
    job_id: str,
    req: ExcelJobDecisionBody,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="excel_registry", action="approve")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Rejects an Excel import job with review notes."""
    j = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Excel import job not found."}})

    j.status = "REJECTED"
    j.reviewed_by = admin.user_id
    j.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    j.review_notes = (req.review_notes if req else None) or "Rejected during review"
    db.commit()

    log_admin_action(db, admin, "REJECT_EXCEL_IMPORT_JOB", "excel_import_jobs", j.id, {"filename": j.filename, "notes": j.review_notes}, request)
    return {"id": j.id, "status": j.status, "review_notes": j.review_notes}


@router.post("/excel-registry/jobs/{job_id}/rollback")
async def rollback_excel_import_job(
    job_id: str,
    req: ExcelJobDecisionBody = None,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.admin, module="excel_registry", action="publish")),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Rolls back a published spreadsheet import job and removes the records created by that batch."""
    j = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Excel import job not found."}})

    if j.status != "PUBLISHED":
        raise HTTPException(status_code=400, detail={"error": {"code": "NOT_PUBLISHED", "message": "Only PUBLISHED import jobs can be rolled back."}})

    rec_ids = j.published_record_ids or []
    removed = 0
    if rec_ids:
        if j.target_dataset == "mandi_prices":
            removed = db.query(MarketPrice).filter(MarketPrice.id.in_(rec_ids)).delete(synchronize_session=False)
        elif j.target_dataset == "mandi_markets":
            removed = db.query(MandiMarket).filter(MandiMarket.id.in_(rec_ids)).delete(synchronize_session=False)
        elif j.target_dataset == "advisories":
            removed = db.query(BroadcastItem).filter(BroadcastItem.id.in_(rec_ids)).delete(synchronize_session=False)
        elif j.target_dataset == "camp_registrations":
            removed = db.query(DataRequest).filter(DataRequest.id.in_(rec_ids)).delete(synchronize_session=False)

    j.status = "ROLLED_BACK"
    if req and req.review_notes:
        j.review_notes = req.review_notes
    db.commit()

    log_admin_action(db, admin, "ROLLBACK_EXCEL_IMPORT_JOB", "excel_import_jobs", j.id, {"filename": j.filename, "removed_records": removed}, request)
    return {"id": j.id, "status": j.status, "removed_records": removed}


