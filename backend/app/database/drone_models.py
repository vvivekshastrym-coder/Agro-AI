"""Persistent records for the approval-gated drone services network.

These records are accessed only through the authenticated FastAPI service. In
particular, document object keys and application payloads are never returned by
the farmer-facing provider directory.
"""
import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index,
    Integer, JSON, Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy.sql import func

from .connection import Base


def _id() -> str:
    return str(uuid.uuid4())


class DroneCompany(Base):
    __tablename__ = "drone_companies"

    id = Column(String, primary_key=True, default=_id)
    owner_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    registered_name = Column(String(180), nullable=False)
    brand_name = Column(String(120), nullable=True)
    representative_name = Column(String(120), nullable=False)
    contact_email = Column(String(255), nullable=True)
    state = Column(String(80), nullable=False)
    district = Column(String(100), nullable=False)
    address = Column(Text, nullable=True)
    business_registration = Column(String(120), nullable=True)
    service_categories = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="pending")
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_drone_companies_status_active", "status", "is_active"),
        Index("ix_drone_companies_location", "state", "district"),
    )


class DronePilot(Base):
    __tablename__ = "drone_pilots"

    id = Column(String, primary_key=True, default=_id)
    owner_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("drone_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(150), nullable=False)
    photo_url = Column(String(500), nullable=True)
    state = Column(String(80), nullable=False)
    district = Column(String(100), nullable=False)
    taluk = Column(String(100), nullable=True)
    village = Column(String(120), nullable=True)
    qualification = Column(String(180), nullable=True)
    certificate_number = Column(String(120), nullable=True)
    certificate_issuer = Column(String(180), nullable=True)
    certificate_expiry = Column(Date, nullable=True)
    credentials_verified = Column(Boolean, nullable=False, default=False)
    years_experience = Column(Integer, nullable=False, default=0)
    languages = Column(JSON, nullable=False, default=list)
    services = Column(JSON, nullable=False, default=list)
    availability = Column(JSON, nullable=False, default=dict)
    price_per_acre = Column(Numeric(10, 2), nullable=True)
    price_per_hour = Column(Numeric(10, 2), nullable=True)
    minimum_booking_amount = Column(Numeric(10, 2), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_drone_pilots_status_active", "status", "is_active"),
        Index("ix_drone_pilots_location", "state", "district", "taluk"),
        Index("ix_drone_pilots_company_owner", "company_id", "owner_user_id"),
        CheckConstraint("years_experience >= 0", name="ck_drone_pilots_experience_nonnegative"),
        CheckConstraint("price_per_acre IS NULL OR price_per_acre >= 0", name="ck_drone_pilots_price_nonnegative"),
    )


class DroneFleet(Base):
    __tablename__ = "drone_fleet"

    id = Column(String, primary_key=True, default=_id)
    pilot_id = Column(String, ForeignKey("drone_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    manufacturer = Column(String(120), nullable=True)
    model = Column(String(150), nullable=False)
    serial_number = Column(String(120), nullable=True)
    registration_number = Column(String(120), nullable=True)
    capabilities = Column(JSON, nullable=False, default=list)
    payload_litres = Column(Numeric(8, 2), nullable=True)
    equipment_details = Column(Text, nullable=True)
    inspection_due = Column(Date, nullable=True)
    status = Column(String(24), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_drone_fleet_suitability", "pilot_id", "status"),
        UniqueConstraint("serial_number", name="uq_drone_fleet_serial_number"),
    )


class DroneServiceArea(Base):
    __tablename__ = "drone_service_areas"

    id = Column(String, primary_key=True, default=_id)
    pilot_id = Column(String, ForeignKey("drone_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(String(80), nullable=False)
    district = Column(String(100), nullable=False)
    taluk = Column(String(100), nullable=True)
    village = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_drone_service_areas_search", "state", "district", "taluk"),
        UniqueConstraint("pilot_id", "state", "district", "taluk", "village", name="uq_drone_service_area"),
    )


class DroneApplication(Base):
    __tablename__ = "drone_applications"

    id = Column(String, primary_key=True, default=_id)
    applicant_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    application_type = Column(String(24), nullable=False)  # individual | company | copilot
    data = Column(JSON, nullable=False, default=dict)
    status = Column(String(40), nullable=False, default="pending")
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_by_admin = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    result_pilot_id = Column(String, ForeignKey("drone_pilots.id", ondelete="SET NULL"), nullable=True)
    result_company_id = Column(String, ForeignKey("drone_companies.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_drone_applications_review_queue", "status", "submitted_at"),
        Index("ix_drone_applications_owner", "applicant_user_id", "submitted_at"),
    )


class DroneDocument(Base):
    __tablename__ = "drone_pilot_documents"

    id = Column(String, primary_key=True, default=_id)
    application_id = Column(String, ForeignKey("drone_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    document_type = Column(String(64), nullable=False)
    object_key = Column(String(500), nullable=False, unique=True)
    original_filename = Column(String(180), nullable=False)
    content_type = Column(String(80), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    verification_status = Column(String(24), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_drone_documents_size"),)


class DroneApprovalHistory(Base):
    __tablename__ = "drone_approval_history"

    id = Column(String, primary_key=True, default=_id)
    application_id = Column(String, ForeignKey("drone_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(40), nullable=False)
    previous_status = Column(String(40), nullable=True)
    new_status = Column(String(40), nullable=False)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DroneBooking(Base):
    __tablename__ = "drone_bookings"

    id = Column(String, primary_key=True, default=_id)
    farmer_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider_pilot_id = Column(String, ForeignKey("drone_pilots.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_drone_id = Column(String, ForeignKey("drone_fleet.id", ondelete="RESTRICT"), nullable=True)
    service_category = Column(String(48), nullable=False)
    farm_state = Column(String(80), nullable=False)
    farm_district = Column(String(100), nullable=False)
    farm_taluk = Column(String(100), nullable=True)
    farm_village = Column(String(120), nullable=True)
    area_acres = Column(Numeric(10, 2), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    quoted_total = Column(Numeric(12, 2), nullable=False)
    price_snapshot = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="requested")
    farmer_notes = Column(Text, nullable=True)
    provider_notes = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_drone_bookings_farmer_created", "farmer_user_id", "requested_at"),
        Index("ix_drone_bookings_pilot_status_date", "provider_pilot_id", "status", "scheduled_date"),
        Index("uq_drone_booking_pilot_day", "provider_pilot_id", "scheduled_date", unique=True,
              postgresql_where=text("status IN ('accepted','pilot_assigned','scheduled','on_the_way','in_progress')"),
              sqlite_where=text("status IN ('accepted','pilot_assigned','scheduled','on_the_way','in_progress')")),
        Index("uq_drone_booking_drone_day", "assigned_drone_id", "scheduled_date", unique=True,
              postgresql_where=text("assigned_drone_id IS NOT NULL AND status IN ('accepted','pilot_assigned','scheduled','on_the_way','in_progress')"),
              sqlite_where=text("assigned_drone_id IS NOT NULL AND status IN ('accepted','pilot_assigned','scheduled','on_the_way','in_progress')")),
        CheckConstraint("area_acres > 0", name="ck_drone_bookings_area_positive"),
        CheckConstraint("quoted_total >= 0", name="ck_drone_bookings_quote_nonnegative"),
    )


class DroneBookingStatusHistory(Base):
    __tablename__ = "drone_booking_status_history"

    id = Column(String, primary_key=True, default=_id)
    booking_id = Column(String, ForeignKey("drone_bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    previous_status = Column(String(32), nullable=True)
    new_status = Column(String(32), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DroneRoleAssignment(Base):
    __tablename__ = "drone_role_assignments"

    id = Column(String, primary_key=True, default=_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("drone_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False, default="pending")
    requested_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_drone_role_assignments_user_status", "user_id", "status"),
        UniqueConstraint("user_id", "company_id", "role", "status", name="uq_drone_role_assignment_state"),
    )


class DroneReview(Base):
    __tablename__ = "drone_reviews"

    id = Column(String, primary_key=True, default=_id)
    booking_id = Column(String, ForeignKey("drone_bookings.id", ondelete="RESTRICT"), nullable=False, unique=True)
    farmer_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    pilot_id = Column(String, ForeignKey("drone_pilots.id", ondelete="RESTRICT"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    review = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_drone_reviews_rating"),)
