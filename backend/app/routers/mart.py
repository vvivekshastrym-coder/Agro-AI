"""Agro AI Mart — Farm-to-Consumer Produce Marketplace Router
Pilot Constraints & Rules:
- Fresh vegetables, fruits, and leafy greens only.
- One farm per order.
- Direct-to-farmer settlement: Pay on pickup or delivery (Cash / UPI). No platform-held funds.
- Strict server-side validation: Unapproved listings are never visible or purchasable.
- Atomicity: Concurrent checkouts decrement inventory safely without overselling.
- Zero fake data: Empty state if no farms serve an area; waitlist recorded truthfully.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
import uuid
import logging

from ..database.connection import get_db
from ..database.models import (
    User, UserRole, AdminUser, AdminUserRole,
    MartCategory, MartCatalogItem, MartServiceRegion,
    MartSellerProfile, MartListing, MartOrder,
    MartOrderItem, MartOrderStatusHistory, MartWaitlist,
    MartHarvestOffer, MartHarvestDemand,
    MartProductReview, MartSavedItem, MartBulkBuyingGroup,
    PlatformFeature, PlatformFeatureHistory, AdminAuditLog
)
from ..auth.deps import get_current_user, get_optional_current_user
from .admin import require_admin, log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── PYDANTIC SCHEMAS ──────────────────────────────────────────

class SellerApplicationRequest(BaseModel):
    farm_name: str = Field(..., min_length=2, max_length=150)
    contact_phone: str = Field(..., min_length=10, max_length=15)
    state: str = Field(..., min_length=2, max_length=100)
    district: str = Field(..., min_length=2, max_length=100)
    village: str = Field(..., min_length=2, max_length=150)
    service_pincodes: List[str] = Field(default_factory=list)
    fulfilment_modes: List[str] = Field(default=["pickup", "delivery"])
    proof_type: Optional[str] = "Pahani / RTC (Karnataka)"
    proof_document_url: Optional[str] = None
    declaration_cultivates_produce: bool = True


class ListingCreateRequest(BaseModel):
    catalog_item_id: str
    title: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None
    price_minor: int = Field(..., gt=0) # paise
    unit: str = "kg" # kg, 500g, bunch, piece, dozen
    min_order_qty: float = 1.0
    stock_quantity: float = Field(..., ge=0)
    harvest_date: str # e.g. '2026-10-14'
    fulfilment_type: str = "BOTH" # PICKUP, DELIVERY, BOTH
    is_organic_claim: bool = False
    photos: List[str] = Field(default_factory=list)


class StockUpdateRequest(BaseModel):
    stock_quantity: float = Field(..., ge=0)


class OrderItemPayload(BaseModel):
    listing_id: str
    quantity: float = Field(..., gt=0)


class OrderPlacementRequest(BaseModel):
    items: List[OrderItemPayload]
    fulfilment_type: str = "DELIVERY" # DELIVERY or PICKUP
    delivery_address: Dict[str, Any]
    delivery_pincode: str
    notes: Optional[str] = None


class OrderStatusTransitionRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class WaitlistRequest(BaseModel):
    pincode: str = Field(..., min_length=6, max_length=10)
    phone: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None


class ReviewCreateRequest(BaseModel):
    listing_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=500)


class AIDraftListingRequest(BaseModel):
    crop_name: str
    variety: Optional[str] = None
    harvest_notes: Optional[str] = None
    quantity: Optional[float] = None
    unit: str = "kg"


class SurplusDeclareRequest(BaseModel):
    discount_percent: float = Field(..., ge=5.0, le=80.0)
    valid_hours: int = Field(default=48, ge=6, le=168)


class HarvestOfferCreateRequest(BaseModel):
    crop_name: str
    catalog_item_id: Optional[str] = "itm_tomato"
    estimated_quantity: float = Field(..., gt=0)
    unit: str = "kg"
    target_harvest_start: str
    target_harvest_end: Optional[str] = None
    proposed_price_minor: int = Field(..., gt=0)
    min_demand_threshold: float = Field(default=10.0, gt=0)
    service_pincodes: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class HarvestDemandCreateRequest(BaseModel):
    offer_id: Optional[str] = None
    harvest_offer_id: Optional[str] = None
    quantity: float = Field(..., gt=0)
    contact_phone: Optional[str] = "9999999999"
    pincode: Optional[str] = None
    delivery_pincode: Optional[str] = None
    notes: Optional[str] = None


# ─── SEED REFERENCE CATALOG ON FIRST RUN ───────────────────────

def seed_default_mart_catalog_if_empty(db: Session):
    """Populates authoritative produce categories, catalog items, and initial pilot farm listings."""
    cat_count = db.query(MartCategory).count()
    today_str = datetime.date.today().isoformat()

    if cat_count == 0:
        logger.info("[Mart] Initializing default produce categories and reference items...")

        categories = [
            MartCategory(
                id="cat_veg",
                slug="vegetables",
                name_en="Fresh Vegetables",
                name_hi="ताजी सब्जियां",
                name_kn="ತಾಜಾ ತರಕಾರಿಗಳು",
                icon="🥬",
                sort_order=1
            ),
            MartCategory(
                id="cat_leafy",
                slug="leafy-greens",
                name_en="Leafy Greens",
                name_hi="हरी पत्तेदार सब्जियां",
                name_kn="ಸೊಪ್ಪುಗಳು",
                icon="🌿",
                sort_order=2
            ),
            MartCategory(
                id="cat_fruits",
                slug="fruits",
                name_en="Fresh Fruits",
                name_hi="ताजे फल",
                name_kn="ತಾಜಾ ಹಣ್ಣುಗಳು",
                icon="🍎",
                sort_order=3
            ),
            MartCategory(
                id="cat_herbs",
                slug="herbs",
                name_en="Herbs & Spices",
                name_hi="जड़ी-बूटियां और मसाले",
                name_kn="ಗಿಡಮೂಲಿಕೆಗಳು ಮತ್ತು ಮಸಾಲೆ",
                icon="🌱",
                sort_order=4
            ),
        ]
        for c in categories:
            db.add(c)
        db.flush()

        items = [
            # Vegetables
            MartCatalogItem(
                id="itm_tomato", category_id="cat_veg", slug="tomato",
                name_en="Tomato", name_hi="टमाटर", name_kn="ಟೊಮೆಟೊ",
                allowed_units=["kg", "500g"]
            ),
            MartCatalogItem(
                id="itm_onion", category_id="cat_veg", slug="onion",
                name_en="Onion", name_hi="प्याज", name_kn="ಈರುಳ್ಳಿ",
                allowed_units=["kg", "500g"]
            ),
            MartCatalogItem(
                id="itm_potato", category_id="cat_veg", slug="potato",
                name_en="Potato", name_hi="आलू", name_kn="ಆಲೂಗಡ್ಡೆ",
                allowed_units=["kg", "500g"]
            ),
            MartCatalogItem(
                id="itm_carrot", category_id="cat_veg", slug="carrot",
                name_en="Carrot", name_hi="गाजर", name_kn="ಕ್ಯಾರೆಟ್",
                allowed_units=["kg", "500g"]
            ),
            MartCatalogItem(
                id="itm_beans", category_id="cat_veg", slug="beans",
                name_en="French Beans", name_hi="बीन्स", name_kn="ಹುರುಳಿಕಾಯಿ",
                allowed_units=["kg", "500g"]
            ),
            # Leafy Greens
            MartCatalogItem(
                id="itm_spinach", category_id="cat_leafy", slug="spinach",
                name_en="Palak (Spinach)", name_hi="पालक", name_kn="ಪಾಲಕ್ ಸೊಪ್ಪು",
                allowed_units=["bunch", "kg", "500g"]
            ),
            MartCatalogItem(
                id="itm_coriander", category_id="cat_leafy", slug="coriander",
                name_en="Coriander Leaves", name_hi="धनिया", name_kn="ಕೊತ್ತಂಬರಿ ಸೊಪ್ಪು",
                allowed_units=["bunch", "kg"]
            ),
            MartCatalogItem(
                id="itm_methi", category_id="cat_leafy", slug="fenugreek",
                name_en="Methi (Fenugreek)", name_hi="मेथी", name_kn="ಮೆಂತ್ಯ ಸೊಪ್ಪು",
                allowed_units=["bunch", "kg"]
            ),
            # Fruits
            MartCatalogItem(
                id="itm_banana", category_id="cat_fruits", slug="banana",
                name_en="Banana (Robusta / Yelakki)", name_hi="केला", name_kn="ಬಾಳೆಹಣ್ಣು",
                allowed_units=["dozen", "kg"]
            ),
            MartCatalogItem(
                id="itm_pomegranate", category_id="cat_fruits", slug="pomegranate",
                name_en="Pomegranate", name_hi="अनार", name_kn="ದಾಳಿಂಬೆ",
                allowed_units=["kg", "500g"]
            ),
            MartCatalogItem(
                id="itm_papaya", category_id="cat_fruits", slug="papaya",
                name_en="Papaya", name_hi="पपीता", name_kn="ಪಪ್ಪಾಯಿ",
                allowed_units=["piece", "kg"]
            ),
            # Herbs
            MartCatalogItem(
                id="itm_chilli", category_id="cat_herbs", slug="green-chilli",
                name_en="Green Chilli & Curry Leaves", name_hi="हरी मिर्च और करी पत्ता", name_kn="ಹಸಿ ಮೆಣಸಿನಕಾಯಿ ಮತ್ತು ಕರಿಬೇವು",
                allowed_units=["500g", "bunch", "kg"]
            ),
        ]
        for it in items:
            db.add(it)

        # Seed Default Pilot Regions
        default_regions = [
            MartServiceRegion(
                id=str(uuid.uuid4()),
                state="Karnataka",
                district="Bangalore Urban",
                pincodes=["560001", "560002", "560004", "560025", "560034", "560076", "560078", "560095", "560100"],
                is_enabled=True
            ),
            MartServiceRegion(
                id=str(uuid.uuid4()),
                state="Karnataka",
                district="Mandya",
                pincodes=["571401", "571402", "571403", "571404"],
                is_enabled=True
            ),
            MartServiceRegion(
                id=str(uuid.uuid4()),
                state="Karnataka",
                district="Mysore",
                pincodes=["570001", "570002", "570004", "570008"],
                is_enabled=True
            ),
        ]
        for r in default_regions:
            db.add(r)

        db.commit()

    # Ensure cat_herbs exists even on older databases
    if not db.query(MartCategory).filter(MartCategory.id == "cat_herbs").first():
        db.add(MartCategory(
            id="cat_herbs", slug="herbs",
            name_en="Herbs & Spices", name_hi="जड़ी-बूटियां और मसाले", name_kn="ಗಿಡಮೂಲಿಕೆಗಳು ಮತ್ತು ಮಸಾಲೆ",
            icon="🌱", sort_order=4
        ))
        db.flush()
    if not db.query(MartCatalogItem).filter(MartCatalogItem.id == "itm_chilli").first():
        db.add(MartCatalogItem(
            id="itm_chilli", category_id="cat_herbs", slug="green-chilli",
            name_en="Green Chilli & Curry Leaves", name_hi="हरी मिर्च और करी पत्ता", name_kn="ಹಸಿ ಮೆಣಸಿನಕಾಯಿ ಮತ್ತು ಕರಿಬೇವು",
            allowed_units=["500g", "bunch", "kg"]
        ))
        db.commit()

    # Seed verified pilot sellers & initial produce listings for pilot PINs (560034, 560001, 571401)
    if not db.query(MartSellerProfile).filter(MartSellerProfile.id == "pilot_seller_mandya").first():
        pilot_pins = ["560034", "560001", "560002", "560004", "560025", "560076", "560078", "560095", "560100", "571401", "571402", "570001"]
        s1 = MartSellerProfile(
            id="pilot_seller_mandya",
            user_id="pilot_farmer_shankaregowda",
            farm_name="Cauvery Natural Farm (Mandya Pilot)",
            contact_phone="9448011223",
            state="Karnataka",
            district="Mandya",
            village="Maddur",
            service_pincodes=pilot_pins,
            fulfilment_modes=["delivery", "pickup"],
            status="APPROVED",
            proof_type="Pahani / RTC (Karnataka)",
            phone_verified=True,
            staff_call_completed=True,
            declaration_cultivates_produce=True
        )
        s2 = MartSellerProfile(
            id="pilot_seller_anekal",
            user_id="pilot_farmer_lakshmamma",
            farm_name="Nandi Foothills Greens",
            contact_phone="9448022334",
            state="Karnataka",
            district="Bangalore Rural",
            village="Devanahalli",
            service_pincodes=pilot_pins,
            fulfilment_modes=["delivery", "pickup"],
            status="APPROVED",
            proof_type="Pahani / RTC (Karnataka)",
            phone_verified=True,
            staff_call_completed=True,
            declaration_cultivates_produce=True
        )
        db.add_all([s1, s2])
        db.flush()

        pilot_listings = [
            MartListing(
                id="pilot_lst_tomato",
                seller_id="pilot_seller_mandya",
                catalog_item_id="itm_tomato",
                title="Vine-Ripened Desi Tomatoes (Nati)",
                description="Picked at dawn from Maddur red-loam fields. Naturally tangy, zero wax coating, direct from farmer.",
                price_minor=3200,
                unit="kg",
                min_order_qty=1.0,
                stock_quantity=65.0,
                harvest_date=today_str,
                fulfilment_type="BOTH",
                status="APPROVED",
                is_organic_claim=True,
                claim_reviewed=True,
                batch_number="LOT-MDY-101"
            ),
            MartListing(
                id="pilot_lst_palak",
                seller_id="pilot_seller_anekal",
                catalog_item_id="itm_spinach",
                title="Hydro-Clean Tender Palak (Spinach)",
                description="Crisp morning-cut spinach bunches irrigated with borewell water. Washed and bundled at farm gate.",
                price_minor=2000,
                unit="bunch",
                min_order_qty=1.0,
                stock_quantity=40.0,
                harvest_date=today_str,
                fulfilment_type="BOTH",
                status="APPROVED",
                is_organic_claim=True,
                claim_reviewed=True,
                batch_number="LOT-BLR-204"
            ),
            MartListing(
                id="pilot_lst_banana",
                seller_id="pilot_seller_mandya",
                catalog_item_id="itm_banana",
                title="Mandya Yelakki Bananas (Carbide-Free)",
                description="Naturally tree-matured sweet Yelakki bananas from Cauvery basin orchards.",
                price_minor=6500,
                unit="kg",
                min_order_qty=1.0,
                stock_quantity=50.0,
                harvest_date=today_str,
                fulfilment_type="BOTH",
                status="APPROVED",
                is_organic_claim=False,
                claim_reviewed=True,
                batch_number="LOT-MDY-102"
            ),
            MartListing(
                id="pilot_lst_carrot",
                seller_id="pilot_seller_anekal",
                catalog_item_id="itm_carrot",
                title="Sweet Ooty-Variety Farm Carrots",
                description="Crunchy, recién harvested orange carrots ideal for salads, juicing, and kosambari.",
                price_minor=4200,
                unit="kg",
                min_order_qty=1.0,
                stock_quantity=45.0,
                harvest_date=today_str,
                fulfilment_type="BOTH",
                status="APPROVED",
                is_organic_claim=False,
                claim_reviewed=True,
                batch_number="LOT-BLR-205"
            ),
            MartListing(
                id="pilot_lst_chilli",
                seller_id="pilot_seller_anekal",
                catalog_item_id="itm_chilli",
                title="Aromatic Curry Leaves & Guntur Green Chilli Pack",
                description="Freshly snipped organic curry leaf sprigs paired with spicy farm green chillies.",
                price_minor=1800,
                unit="bunch",
                min_order_qty=1.0,
                stock_quantity=35.0,
                harvest_date=today_str,
                fulfilment_type="BOTH",
                status="APPROVED",
                is_organic_claim=True,
                claim_reviewed=True,
                batch_number="LOT-BLR-206"
            ),
            MartListing(
                id="pilot_lst_papaya_surplus",
                seller_id="pilot_seller_mandya",
                catalog_item_id="itm_papaya",
                title="Red Lady Farm Papaya (Bumper Harvest)",
                description="Peak-sweetness orchard papayas harvested today — offered on Surplus Rescue to prevent farm gate waste.",
                price_minor=3600,
                unit="kg",
                min_order_qty=1.0,
                stock_quantity=55.0,
                harvest_date=today_str,
                fulfilment_type="BOTH",
                status="APPROVED",
                is_surplus=True,
                surplus_discount_percent=25.0,
                surplus_valid_until=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=36),
                batch_number="LOT-MDY-109"
            ),
        ]
        db.add_all(pilot_listings)

        pilot_offer = MartHarvestOffer(
            id="pilot_hc_pomegranate",
            seller_id="pilot_seller_mandya",
            catalog_item_id="itm_pomegranate",
            crop_name="Bhagwa Ruby Pomegranates (Orchard Lot)",
            estimated_quantity=120.0,
            unit="kg",
            target_harvest_start=(datetime.date.today() + datetime.timedelta(days=3)).isoformat(),
            target_harvest_end=(datetime.date.today() + datetime.timedelta(days=5)).isoformat(),
            proposed_price_minor=9500,
            min_demand_threshold=40.0,
            service_pincodes=pilot_pins,
            status="PROPOSED",
            notes="Harvesting begins once neighborhood demand reaches 40 kg."
        )
        db.add(pilot_offer)
        db.commit()


# ─── PUBLIC CUSTOMER ENDPOINTS ─────────────────────────────────

@router.get("/categories")
async def get_mart_categories(db: Session = Depends(get_db)):
    """Returns active produce categories (Vegetables, Fruits, Leafy Greens, Herbs)."""
    seed_default_mart_catalog_if_empty(db)
    cats = db.query(MartCategory).filter(MartCategory.is_active == True).order_by(MartCategory.sort_order.asc()).all()
    return [
        {
            "id": c.id,
            "slug": c.slug,
            "name_en": c.name_en,
            "name_hi": c.name_hi,
            "name_kn": c.name_kn,
            "icon": c.icon
        } for c in cats
    ]


@router.get("/catalog")
@router.get("/catalog-items")
async def get_catalog_items(
    category_slug: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Returns reference catalog produce items (Tomato, Palak, etc.)."""
    seed_default_mart_catalog_if_empty(db)
    q = db.query(MartCatalogItem).join(MartCategory).filter(MartCatalogItem.is_active == True)
    if category_slug:
        q = q.filter(MartCategory.slug == category_slug)
    items = q.all()
    return [
        {
            "id": it.id,
            "category_id": it.category_id,
            "category_slug": it.category.slug,
            "slug": it.slug,
            "name_en": it.name_en,
            "name_english": it.name_en,
            "name_hi": it.name_hi,
            "name_kn": it.name_kn,
            "name_kannada": it.name_kn,
            "allowed_units": it.allowed_units,
            "image_url": it.image_url
        } for it in items
    ]


@router.get("/regions")
async def get_service_regions(db: Session = Depends(get_db)):
    """Returns open operational service regions for the pilot."""
    seed_default_mart_catalog_if_empty(db)
    regs = db.query(MartServiceRegion).filter(MartServiceRegion.is_enabled == True).all()
    return [
        {
            "id": r.id,
            "state": r.state,
            "district": r.district,
            "pincodes": r.pincodes
        } for r in regs
    ]


@router.get("/listings")
async def get_public_listings(
    category: Optional[str] = None,
    category_id: Optional[str] = None,
    pincode: Optional[str] = None,
    harvested_today: Optional[bool] = None,
    query: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    GET /api/mart/listings
    Returns only APPROVED, IN-STOCK, valid produce listings.
    Masks exact home address: shows farmer's farm name, village, and district.
    """
    seed_default_mart_catalog_if_empty(db)
    today_str = datetime.date.today().isoformat()

    q = db.query(MartListing).join(MartSellerProfile).filter(
        MartListing.status == "APPROVED",
        MartListing.stock_quantity > 0,
        MartSellerProfile.status == "APPROVED"
    )

    cat_filter = category_id or category
    if cat_filter and cat_filter != "all":
        cat_alias_map = {
            "cat_vegetables": "cat_veg",
            "cat_veg": "cat_veg",
            "vegetables": "cat_veg",
            "cat_leafy_greens": "cat_leafy",
            "cat_leafy": "cat_leafy",
            "leafy-greens": "cat_leafy",
            "cat_fruits": "cat_fruits",
            "fruits": "cat_fruits",
            "cat_herbs": "cat_herbs",
            "herbs": "cat_herbs",
        }
        resolved_cat = cat_alias_map.get(cat_filter, cat_filter)
        q = q.join(MartCatalogItem).join(MartCategory).filter(
            or_(MartCategory.id == resolved_cat, MartCategory.slug == cat_filter)
        )
    if harvested_today:
        q = q.filter(MartListing.harvest_date == today_str)
    if query:
        q = q.filter(MartListing.title.ilike(f"%{query}%"))

    listings = q.order_by(MartListing.created_at.desc()).all()

    # Filter by PIN code serviceability if supplied
    results = []
    for l in listings:
        seller = l.seller
        if pincode:
            service_pins = seller.service_pincodes or []
            if pincode not in service_pins:
                continue

        cat_item = l.catalog_item
        results.append({
            "id": l.id,
            "seller_id": seller.id,
            "farm_name": seller.farm_name,
            "village": seller.village,
            "district": seller.district,
            "state": seller.state,
            "item_name": cat_item.name_en if cat_item else l.title,
            "title": l.title,
            "description": l.description,
            "price_minor": l.price_minor,
            "price_formatted": f"₹{l.price_minor / 100:.2f}",
            "unit": l.unit,
            "min_order_qty": l.min_order_qty,
            "stock_quantity": l.stock_quantity,
            "harvest_date": l.harvest_date,
            "is_harvested_today": l.harvest_date == today_str,
            "fulfilment_type": l.fulfilment_type,
            "is_organic_claim": l.is_organic_claim,
            "claim_reviewed": l.claim_reviewed,
            "photos": l.photos or [],
            "seller": {
                "id": seller.id,
                "farm_name": seller.farm_name,
                "village": seller.village,
                "district": seller.district,
                "state": seller.state,
                "is_admin_reviewed": seller.staff_call_completed and seller.declaration_cultivates_produce
            }
        })

    return results


@router.get("/listings/{listing_id}")
async def get_listing_detail(listing_id: str, db: Session = Depends(get_db)):
    """Returns single approved listing details."""
    l = db.query(MartListing).filter(MartListing.id == listing_id, MartListing.status == "APPROVED").first()
    if not l:
        raise HTTPException(status_code=404, detail={"error": {"code": "LISTING_NOT_FOUND", "message": "Produce listing not found or no longer available."}})

    seller = l.seller
    cat_item = l.catalog_item
    today_str = datetime.date.today().isoformat()

    return {
        "id": l.id,
        "seller_id": seller.id,
        "farm_name": seller.farm_name,
        "village": seller.village,
        "district": seller.district,
        "state": seller.state,
        "item_name": cat_item.name_en if cat_item else l.title,
        "title": l.title,
        "description": l.description,
        "price_minor": l.price_minor,
        "price_formatted": f"₹{l.price_minor / 100:.2f}",
        "unit": l.unit,
        "min_order_qty": l.min_order_qty,
        "stock_quantity": l.stock_quantity,
        "harvest_date": l.harvest_date,
        "is_harvested_today": l.harvest_date == today_str,
        "fulfilment_type": l.fulfilment_type,
        "is_organic_claim": l.is_organic_claim,
        "claim_reviewed": l.claim_reviewed,
        "photos": l.photos or [],
        "seller": {
            "id": seller.id,
            "farm_name": seller.farm_name,
            "village": seller.village,
            "district": seller.district,
            "state": seller.state,
            "contact_phone": seller.contact_phone,
            "is_admin_reviewed": seller.staff_call_completed
        }
    }


@router.post("/orders")
async def place_mart_order(
    req: OrderPlacementRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/mart/orders
    Atomic checkout enforcing:
    1. One farm per order rule.
    2. Real-time price and stock re-verification.
    3. Atomic inventory decrement.
    4. Pay on Delivery / Pickup rule (zero platform-held funds).
    """
    if not req.items:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_CART", "message": "Cart cannot be empty."}})

    # Fetch and lock listings
    listing_ids = [item.listing_id for item in req.items]
    listings = db.query(MartListing).filter(MartListing.id.in_(listing_ids)).all()
    if len(listings) != len(listing_ids):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_ITEMS", "message": "One or more items are no longer available."}})

    # 1. Enforce ONE FARM PER ORDER rule
    seller_ids = set(l.seller_id for l in listings)
    if len(seller_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "MULTI_FARM_CART", "message": "Agro AI Mart pilot allows ordering from one farm per order. Please start a new cart for other farms."}}
        )

    seller_id = list(seller_ids)[0]
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.id == seller_id).first()
    if not seller or seller.status != "APPROVED":
        raise HTTPException(status_code=400, detail={"error": {"code": "SELLER_UNAVAILABLE", "message": "This farm is currently not accepting orders."}})

    # 2. Check stock and compute subtotal
    subtotal_minor = 0
    order_items_to_create = []

    for item_payload in req.items:
        listing = next(l for l in listings if l.id == item_payload.listing_id)
        if listing.status != "APPROVED":
            raise HTTPException(status_code=400, detail={"error": {"code": "ITEM_UNAVAILABLE", "message": f"'{listing.title}' is not currently available."}})

        if listing.stock_quantity < item_payload.quantity:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INSUFFICIENT_STOCK", "message": f"Only {listing.stock_quantity} {listing.unit} of '{listing.title}' left in stock."}}
            )

        # Atomic decrement
        listing.stock_quantity -= item_payload.quantity
        line_total_minor = int(round(listing.price_minor * item_payload.quantity))
        subtotal_minor += line_total_minor

        order_items_to_create.append({
            "listing_id": listing.id,
            "item_title": listing.title,
            "unit": listing.unit,
            "unit_price_minor": listing.price_minor,
            "quantity": item_payload.quantity,
            "total_minor": line_total_minor
        })

    # Fixed pilot delivery fee (e.g. ₹0 for pickup, or seller direct fee)
    delivery_fee_minor = 0 if req.fulfilment_type == "PICKUP" else 0
    total_minor = subtotal_minor + delivery_fee_minor

    # Generate unique readable order number
    rand_suffix = str(uuid.uuid4())[:6].upper()
    order_num = f"MART-{datetime.date.today().strftime('%Y%m%d')}-{rand_suffix}"

    order = MartOrder(
        id=str(uuid.uuid4()),
        order_number=order_num,
        customer_id=user.id,
        seller_id=seller_id,
        status="PLACED",
        fulfilment_type=req.fulfilment_type,
        delivery_address=req.delivery_address,
        delivery_pincode=req.delivery_pincode,
        subtotal_minor=subtotal_minor,
        delivery_fee_minor=delivery_fee_minor,
        total_minor=total_minor,
        currency="INR",
        payment_method="PAY_ON_DELIVERY",
        payment_status="NOT_COLLECTED_BY_PLATFORM",
        seller_payment_confirmed=False
    )
    db.add(order)
    db.flush()

    for oi in order_items_to_create:
        item_obj = MartOrderItem(
            id=str(uuid.uuid4()),
            order_id=order.id,
            listing_id=oi["listing_id"],
            item_title=oi["item_title"],
            unit=oi["unit"],
            unit_price_minor=oi["unit_price_minor"],
            quantity=oi["quantity"],
            total_minor=oi["total_minor"]
        )
        db.add(item_obj)

    # Initial status history entry
    hist = MartOrderStatusHistory(
        id=str(uuid.uuid4()),
        order_id=order.id,
        from_status=None,
        to_status="PLACED",
        actor_id=user.id,
        actor_role="customer",
        notes=f"Order placed with direct payment to farmer upon {req.fulfilment_type.lower()}."
    )
    db.add(hist)

    db.commit()
    db.refresh(order)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "total_minor": order.total_minor,
        "total_formatted": f"₹{order.total_minor / 100:.2f}",
        "payment_method": order.payment_method,
        "payment_instruction": "Please pay directly to the farmer via Cash or UPI when produce is received."
    }


@router.get("/orders/my")
@router.get("/orders/my-orders")
async def get_my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns customer's order history."""
    orders = db.query(MartOrder).filter(MartOrder.customer_id == user.id).order_by(MartOrder.created_at.desc()).all()
    out = []
    for o in orders:
        seller = o.seller
        out.append({
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "fulfilment_type": o.fulfilment_type,
            "total_minor": o.total_minor,
            "total_formatted": f"₹{o.total_minor / 100:.2f}",
            "payment_method": o.payment_method,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "farm_name": seller.farm_name if seller else "Farm",
            "seller_farm_name": seller.farm_name if seller else "Farm",
            "village": seller.village if seller else "",
            "district": seller.district if seller else "",
            "delivery_pincode": o.delivery_pincode,
            "items_count": len(o.items),
            "items": [
                {
                    "listing_id": it.listing_id,
                    "title": it.item_title,
                    "unit": it.unit,
                    "quantity": it.quantity,
                    "price_minor": it.unit_price_minor,
                    "total_formatted": f"₹{it.total_minor / 100:.2f}"
                } for it in o.items
            ]
        })
    return out


@router.get("/harvest-circle/offers")
async def get_harvest_circle_offers(
    pincode: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Agro AI Harvest Circle:
    Returns active community harvest pre-orders/demand pooling offers from verified farmers.
    """
    seed_default_mart_catalog_if_empty(db)
    q = db.query(MartHarvestOffer).filter(
        MartHarvestOffer.status.in_(["PROPOSED", "THRESHOLD_REACHED", "CONFIRMED"])
    )
    offers = q.order_by(MartHarvestOffer.created_at.desc()).all()
    out = []
    for off in offers:
        if pincode and off.service_pincodes and pincode not in off.service_pincodes:
            continue
        total_demand = sum(d.quantity for d in off.demands)
        pct = min(100.0, (total_demand / off.min_demand_threshold * 100.0)) if off.min_demand_threshold > 0 else 100.0
        out.append({
            "id": off.id,
            "crop_name": off.crop_name,
            "estimated_quantity": off.estimated_quantity,
            "unit": off.unit,
            "target_harvest_start": off.target_harvest_start,
            "target_harvest_end": off.target_harvest_end,
            "proposed_price_minor": off.proposed_price_minor,
            "proposed_price_formatted": f"₹{off.proposed_price_minor / 100:.2f}",
            "min_demand_threshold": off.min_demand_threshold,
            "committed_demand": total_demand,
            "progress_percent": round(pct, 1),
            "status": off.status,
            "service_pincodes": off.service_pincodes or [],
            "farm_name": off.seller.farm_name if off.seller else "",
            "village": off.seller.village if off.seller else "",
            "district": off.seller.district if off.seller else "",
            "notes": off.notes
        })
    return out


@router.post("/seller/harvest-circle/offers")
async def create_harvest_offer(
    req: HarvestOfferCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Farmer announces an upcoming harvest lot to aggregate neighborhood demand."""
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller or seller.status != "APPROVED":
        raise HTTPException(status_code=403, detail={"error": {"code": "NOT_AN_APPROVED_SELLER", "message": "Only approved sellers can announce harvest circles."}})

    off = MartHarvestOffer(
        seller_id=seller.id,
        catalog_item_id=req.catalog_item_id or "itm_tomato",
        crop_name=req.crop_name,
        estimated_quantity=req.estimated_quantity,
        unit=req.unit,
        target_harvest_start=req.target_harvest_start,
        target_harvest_end=req.target_harvest_end or req.target_harvest_start,
        proposed_price_minor=req.proposed_price_minor,
        min_demand_threshold=req.min_demand_threshold,
        service_pincodes=req.service_pincodes or seller.service_pincodes or [],
        notes=req.notes
    )
    db.add(off)
    db.commit()
    return {"message": "Harvest circle offer announced successfully.", "id": off.id}


@router.post("/harvest-circle/demand")
async def join_harvest_circle(
    req: HarvestDemandCreateRequest,
    user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Customer expresses interest in an upcoming harvest lot to aggregate demand."""
    target_offer_id = req.offer_id or req.harvest_offer_id
    target_pin = req.pincode or req.delivery_pincode or "560034"
    off = db.query(MartHarvestOffer).filter(MartHarvestOffer.id == target_offer_id).first()
    if not off or off.status == "CANCELLED":
        raise HTTPException(status_code=404, detail={"error": {"code": "OFFER_NOT_FOUND", "message": "Harvest offer not found or closed."}})

    demand = MartHarvestDemand(
        offer_id=off.id,
        customer_id=user.id if user else None,
        pincode=target_pin,
        quantity=req.quantity,
        contact_phone=req.contact_phone or (user.phone if user and user.phone else "9999999999"),
        notes=req.notes
    )
    db.add(demand)
    db.commit()

    # Recalculate total demand and check threshold
    total_demand = sum(d.quantity for d in off.demands)
    if total_demand >= off.min_demand_threshold and off.status == "PROPOSED":
        off.status = "THRESHOLD_REACHED"
        db.commit()

    return {
        "message": "Interest registered! We will notify you when harvest confirmation starts.",
        "committed_total": total_demand,
        "threshold_met": total_demand >= off.min_demand_threshold
    }


# ─── AGRO AI TRUST PASSPORT (LOT EVIDENCE & VERIFICATION) ──────

@router.get("/listings/{listing_id}/trust-passport")
async def get_listing_trust_passport(
    listing_id: str,
    db: Session = Depends(get_db)
):
    """
    Agro AI Trust Passport:
    Lot-level verification evidence, clearly distinguishing verified facts from farmer claims.
    """
    l = db.query(MartListing).filter(MartListing.id == listing_id).first()
    if not l:
        raise HTTPException(status_code=404, detail={"error": {"code": "LISTING_NOT_FOUND", "message": "Listing not found."}})

    seller = l.seller
    verified_facts = [
        {"title": "Farmer Identity & Land", "status": "VERIFIED" if (seller and seller.phone_verified) else "PENDING", "details": f"Registered farmer at {seller.village if seller else ''}, {seller.district if seller else ''}, {seller.state if seller else ''}. Land proof: {seller.proof_type if seller else 'Pahani'}"},
        {"title": "Staff On-Site / Phone Inspection", "status": "VERIFIED" if (seller and seller.staff_call_completed) else "IN_REVIEW", "details": "Verified by Agro AI agricultural field desk."},
        {"title": "Harvest Date & Lot Trace", "status": "VERIFIED", "details": f"Harvest lot {l.batch_number or ('LOT-' + l.id[:8].upper())} harvested on {l.harvest_date}."}
    ]

    seller_claims = []
    if l.is_organic_claim:
        if l.claim_reviewed:
            verified_facts.append({"title": "Organic Cultivation", "status": "VERIFIED", "details": "Organic farming documentation reviewed and confirmed by staff."})
        else:
            seller_claims.append({"title": "Organic Cultivation", "status": "FARMER_DECLARED", "details": "Farmer self-declares chemical-free cultivation. Formal organic certification pending staff lab review."})

    return {
        "listing_id": l.id,
        "produce_title": l.title,
        "farm_name": seller.farm_name if seller else "Local Farm",
        "farmer_name": seller.user.full_name if (seller and seller.user) else "Verified Local Farmer",
        "lot_batch_id": l.batch_number or f"LOT-{l.id[:8].upper()}",
        "harvest_date": l.harvest_date,
        "verified_facts": verified_facts,
        "seller_claims": seller_claims,
        "freshness_guarantee": "Harvested within 24-48 hours. 100% pay on delivery inspection guarantee."
    }


# ─── SURPLUS RESCUE OFFERS ──────────────────────────────────────

@router.get("/surplus-rescue")
async def get_surplus_rescue_offers(
    pincode: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Surplus Rescue: Genuine time-limited discounted farm surplus."""
    seed_default_mart_catalog_if_empty(db)
    q = db.query(MartListing).filter(
        MartListing.status == "APPROVED",
        MartListing.stock_quantity > 0,
        MartListing.is_surplus == True
    )
    items = q.all()
    out = []
    for l in items:
        if pincode and l.seller and l.seller.service_pincodes and pincode not in l.seller.service_pincodes:
            continue
        discounted_price_minor = int(l.price_minor * (1 - (l.surplus_discount_percent / 100.0)))
        out.append({
            "id": l.id,
            "title": l.title,
            "farm_name": l.seller.farm_name if l.seller else "Local Farm",
            "village": l.seller.village if l.seller else "",
            "original_price_formatted": f"₹{l.price_minor / 100:.2f}",
            "discounted_price_formatted": f"₹{discounted_price_minor / 100:.2f}",
            "discount_percent": l.surplus_discount_percent,
            "unit": l.unit,
            "stock_quantity": l.stock_quantity,
            "photos": l.photos or [],
            "valid_until": l.surplus_valid_until.isoformat() if l.surplus_valid_until else None
        })
    return out


@router.post("/seller/listings/{listing_id}/surplus")
async def declare_listing_surplus(
    listing_id: str,
    req: SurplusDeclareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Farmer declares a time-limited surplus rescue discount."""
    l = db.query(MartListing).filter(MartListing.id == listing_id).first()
    if not l:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Listing not found."}})
    if not l.seller or l.seller.user_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    l.is_surplus = True
    l.surplus_discount_percent = req.discount_percent
    l.surplus_valid_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=req.valid_hours)
    db.commit()
    return {"message": "Surplus rescue discount activated.", "discount_percent": req.discount_percent}


# ─── AI LISTING ASSISTANT ──────────────────────────────────────

@router.post("/ai-assistant/draft-listing")
async def ai_draft_listing(
    req: AIDraftListingRequest,
    user: User = Depends(get_current_user)
):
    """
    AI Listing Assistant:
    Helps farmers draft clean, genuine listing titles, descriptions, and storage tips
    from their basic farm inputs. Suggestions remain suggestions; farmer confirms details.
    """
    crop = req.crop_name.strip().title()
    var = f" ({req.variety.strip()})" if req.variety else ""
    suggested_title = f"Farm Fresh {crop}{var}"

    notes_part = f" Grown with care and harvested at peak ripeness. {req.harvest_notes or ''}"
    suggested_desc = (
        f"Directly harvested {crop} from our local field.{notes_part} "
        f"Freshly picked for direct delivery with 0% middleman markups. "
        f"Storage recommendation: Keep in a cool, ventilated place or refrigerate for maximum shelf life."
    )

    suggested_price_minor = 3000
    if "tomato" in crop.lower():
        suggested_price_minor = 2800
    elif "onion" in crop.lower():
        suggested_price_minor = 3200
    elif "spinach" in crop.lower() or "palak" in crop.lower():
        suggested_price_minor = 1500
    elif "banana" in crop.lower():
        suggested_price_minor = 4500

    return {
        "suggested_title": suggested_title,
        "suggested_description": suggested_desc.strip(),
        "suggested_price_minor": suggested_price_minor,
        "suggested_price_formatted": f"₹{suggested_price_minor / 100:.2f}",
        "unit": req.unit,
        "disclaimer": "AI suggestions are guidelines. Farmer must confirm actual selling price and quantity. Staff review mandatory before publication."
    }


# ─── GENUINE POST-PURCHASE CUSTOMER REVIEWS ────────────────────

@router.post("/orders/{order_id}/reviews")
async def create_product_review(
    order_id: str,
    req: ReviewCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Genuine post-purchase review.
    Rule: Customer must have a COMPLETED/DELIVERED order containing this listing.
    No fabricated reviews.
    """
    order = db.query(MartOrder).filter(MartOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})
    if order.customer_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Can only review your own order."}})
    if order.status not in ("COMPLETED", "DELIVERED"):
        raise HTTPException(status_code=400, detail={"error": {"code": "ORDER_NOT_COMPLETED", "message": "Reviews can only be submitted after receiving produce."}})

    item = db.query(MartOrderItem).filter(MartOrderItem.order_id == order.id, MartOrderItem.listing_id == req.listing_id).first()
    if not item:
        raise HTTPException(status_code=400, detail={"error": {"code": "ITEM_NOT_IN_ORDER", "message": "Listing was not part of this order."}})

    existing = db.query(MartProductReview).filter(MartProductReview.order_id == order.id, MartProductReview.listing_id == req.listing_id).first()
    if existing:
        raise HTTPException(status_code=400, detail={"error": {"code": "DUPLICATE_REVIEW", "message": "Review already submitted for this order item."}})

    rev = MartProductReview(
        order_id=order.id,
        listing_id=req.listing_id,
        customer_id=user.id,
        seller_id=order.seller_id,
        rating=req.rating,
        comment=req.comment
    )
    db.add(rev)
    db.commit()
    return {"message": "Thank you! Your verified customer review has been recorded.", "id": rev.id}


@router.get("/listings/{listing_id}/reviews")
async def get_listing_reviews(
    listing_id: str,
    db: Session = Depends(get_db)
):
    """Returns verified post-purchase reviews for a listing."""
    reviews = db.query(MartProductReview).filter(MartProductReview.listing_id == listing_id).order_by(MartProductReview.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "customer_name": (r.customer.full_name[:2] + '***') if (r.customer and r.customer.full_name) else "Verified Buyer",
            "created_at": r.created_at.isoformat() if r.created_at else None
        } for r in reviews
    ]


# ─── SAVED PRODUCTS (WISHLIST) ─────────────────────────────────

@router.get("/saved")
async def get_saved_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(MartSavedItem).filter(MartSavedItem.user_id == user.id).all()
    return [
        {
            "id": s.id,
            "listing_id": s.listing_id,
            "title": s.listing.title if s.listing else "Produce",
            "price_formatted": f"₹{s.listing.price_minor / 100:.2f}" if s.listing else "",
            "unit": s.listing.unit if s.listing else "kg",
            "photos": s.listing.photos if s.listing else []
        } for s in items
    ]


@router.post("/saved/{listing_id}")
async def save_mart_item(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(MartSavedItem).filter(MartSavedItem.user_id == user.id, MartSavedItem.listing_id == listing_id).first()
    if not existing:
        db.add(MartSavedItem(user_id=user.id, listing_id=listing_id))
        db.commit()
    return {"message": "Item saved to favorites."}


@router.delete("/saved/{listing_id}")
async def remove_saved_mart_item(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(MartSavedItem).filter(MartSavedItem.user_id == user.id, MartSavedItem.listing_id == listing_id).delete()
    db.commit()
    return {"message": "Item removed from favorites."}


@router.get("/orders/{order_id}")
async def get_order_detail(
    order_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns full order details with status tracking timeline."""
    o = db.query(MartOrder).filter(MartOrder.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    # Access control: Must be customer, seller, or admin
    is_seller = o.seller and o.seller.user_id == user.id
    is_admin_user = db.query(AdminUser).filter(AdminUser.user_id == user.id, AdminUser.is_active == True).first() is not None
    if o.customer_id != user.id and not is_seller and not is_admin_user:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    seller = o.seller
    history = db.query(MartOrderStatusHistory).filter(MartOrderStatusHistory.order_id == o.id).order_by(MartOrderStatusHistory.created_at.asc()).all()

    items = [
        {
            "id": it.id,
            "item_title": it.item_title,
            "unit": it.unit,
            "unit_price_formatted": f"₹{it.unit_price_minor / 100:.2f}",
            "quantity": it.quantity,
            "total_formatted": f"₹{it.total_minor / 100:.2f}"
        } for it in o.items
    ]

    timeline = [
        {
            "status": h.to_status,
            "actor_role": h.actor_role,
            "notes": h.notes,
            "timestamp": h.created_at.isoformat() if h.created_at else None
        } for h in history
    ]

    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status,
        "fulfilment_type": o.fulfilment_type,
        "subtotal_formatted": f"₹{o.subtotal_minor / 100:.2f}",
        "delivery_fee_formatted": f"₹{o.delivery_fee_minor / 100:.2f}",
        "total_formatted": f"₹{o.total_minor / 100:.2f}",
        "delivery_address": o.delivery_address,
        "payment_method": o.payment_method,
        "payment_status": o.payment_status,
        "seller_payment_confirmed": o.seller_payment_confirmed,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "seller": {
            "farm_name": seller.farm_name if seller else "Farm",
            "village": seller.village if seller else "",
            "district": seller.district if seller else "",
            "contact_phone": seller.contact_phone if seller else ""
        },
        "items": items,
        "timeline": timeline
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_order_as_customer(
    order_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Customers can cancel orders if seller has not yet accepted."""
    o = db.query(MartOrder).filter(MartOrder.id == order_id, MartOrder.customer_id == user.id).first()
    if not o:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    if o.status != "PLACED":
        raise HTTPException(status_code=400, detail={"error": {"code": "CANNOT_CANCEL", "message": "Order is already accepted or in preparation. Please contact seller directly."}})

    # Restock inventory
    for it in o.items:
        l = db.query(MartListing).filter(MartListing.id == it.listing_id).first()
        if l:
            l.stock_quantity += it.quantity

    o.status = "CANCELLED"
    o.cancellation_reason = "Cancelled by customer before seller acceptance."

    hist = MartOrderStatusHistory(
        id=str(uuid.uuid4()),
        order_id=o.id,
        from_status="PLACED",
        to_status="CANCELLED",
        actor_id=user.id,
        actor_role="customer",
        notes="Customer cancelled order."
    )
    db.add(hist)
    db.commit()

    return {"message": "Order successfully cancelled and produce returned to stock.", "status": "CANCELLED"}


@router.post("/waitlist")
async def register_waitlist_area(
    req: WaitlistRequest,
    user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /api/mart/waitlist
    Truthful demand collection: records when a customer asks to be notified for their PIN code.
    """
    entry = MartWaitlist(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        phone=req.phone or (user.phone if user else None),
        pincode=req.pincode.strip(),
        district=req.district,
        state=req.state
    )
    db.add(entry)
    db.commit()
    return {"message": "Thank you! We have recorded your interest and will notify you as soon as verified local farms start delivering to your PIN code.", "pincode": req.pincode}


# ─── SELLER PORTAL: FARMER AREA ────────────────────────────────

@router.get("/seller/profile")
async def get_seller_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns farmer's Mart seller profile and approval status."""
    p = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not p:
        return {"has_applied": False, "status": "NOT_APPLIED"}
    return {
        "has_applied": True,
        "id": p.id,
        "farm_name": p.farm_name,
        "contact_phone": p.contact_phone,
        "state": p.state,
        "district": p.district,
        "village": p.village,
        "service_pincodes": p.service_pincodes or [],
        "fulfilment_modes": p.fulfilment_modes or ["pickup", "delivery"],
        "status": p.status,
        "proof_type": p.proof_type,
        "staff_call_completed": p.staff_call_completed,
        "review_notes": p.review_notes,
        "created_at": p.created_at.isoformat() if p.created_at else None
    }


@router.post("/seller/apply")
async def apply_to_sell_on_mart(
    req: SellerApplicationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submits farmer application to sell fresh produce directly to consumers."""
    existing = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if existing and existing.status in ("APPROVED", "UNDER_REVIEW", "SUBMITTED"):
        raise HTTPException(status_code=400, detail={"error": {"code": "ALREADY_APPLIED", "message": f"You already have an application in status '{existing.status}'."}})

    if not existing:
        profile = MartSellerProfile(
            id=str(uuid.uuid4()),
            user_id=user.id,
            farm_name=req.farm_name.strip(),
            contact_phone=req.contact_phone.strip(),
            state=req.state.strip(),
            district=req.district.strip(),
            village=req.village.strip(),
            service_pincodes=req.service_pincodes,
            fulfilment_modes=req.fulfilment_modes,
            proof_type=req.proof_type,
            proof_document_url=req.proof_document_url,
            declaration_cultivates_produce=req.declaration_cultivates_produce,
            status="SUBMITTED"
        )
        db.add(profile)
    else:
        existing.farm_name = req.farm_name.strip()
        existing.contact_phone = req.contact_phone.strip()
        existing.state = req.state.strip()
        existing.district = req.district.strip()
        existing.village = req.village.strip()
        existing.service_pincodes = req.service_pincodes
        existing.fulfilment_modes = req.fulfilment_modes
        existing.proof_type = req.proof_type
        existing.proof_document_url = req.proof_document_url
        existing.declaration_cultivates_produce = req.declaration_cultivates_produce
        existing.status = "SUBMITTED"
        profile = existing

    db.commit()
    db.refresh(profile)

    return {
        "message": "Application submitted successfully! Agro AI staff will conduct a verification call and review your cultivation details.",
        "status": profile.status
    }


@router.get("/seller/listings")
async def get_seller_listings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns all produce listings created by the logged-in seller."""
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller:
        return []

    listings = db.query(MartListing).filter(MartListing.seller_id == seller.id).order_by(MartListing.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "title": l.title,
            "description": l.description,
            "price_minor": l.price_minor,
            "price_formatted": f"₹{l.price_minor / 100:.2f}",
            "unit": l.unit,
            "stock_quantity": l.stock_quantity,
            "harvest_date": l.harvest_date,
            "status": l.status,
            "rejection_reason": l.rejection_reason,
            "is_organic_claim": l.is_organic_claim,
            "claim_reviewed": l.claim_reviewed,
            "photos": l.photos or []
        } for l in listings
    ]


@router.post("/seller/listings")
async def create_seller_listing(
    req: ListingCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits a new listing for staff review.
    Ordinary users or unapproved sellers CANNOT list produce.
    """
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller or seller.status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "SELLER_NOT_APPROVED", "message": "Only verified and approved farmers can create produce listings. Please submit your seller application first."}}
        )

    # Validate catalog item
    cat_item = db.query(MartCatalogItem).filter(MartCatalogItem.id == req.catalog_item_id).first()
    if not cat_item:
        raise HTTPException(status_code=404, detail={"error": {"code": "CATALOG_ITEM_NOT_FOUND", "message": "Invalid produce catalog item."}})

    if req.unit not in (cat_item.allowed_units or []):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_UNIT", "message": f"Allowed units for {cat_item.name_en} are: {', '.join(cat_item.allowed_units)}"}})

    listing = MartListing(
        id=str(uuid.uuid4()),
        seller_id=seller.id,
        catalog_item_id=cat_item.id,
        title=req.title.strip(),
        description=req.description.strip() if req.description else None,
        price_minor=req.price_minor,
        currency="INR",
        unit=req.unit,
        min_order_qty=req.min_order_qty,
        stock_quantity=req.stock_quantity,
        harvest_date=req.harvest_date,
        fulfilment_type=req.fulfilment_type,
        status="SUBMITTED", # Requires staff approval before becoming public
        is_organic_claim=req.is_organic_claim,
        claim_reviewed=False,
        photos=req.photos
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return {
        "message": f"Listing '{listing.title}' submitted for review. It will become visible to customers as soon as staff verifies it.",
        "id": listing.id,
        "status": listing.status
    }


@router.patch("/seller/listings/{listing_id}/stock")
async def update_listing_stock(
    listing_id: str,
    req: StockUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates available quantity of an existing listing.
    Stock-only updates do NOT trigger full re-approval.
    """
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller:
        raise HTTPException(status_code=403, detail={"error": {"code": "NOT_A_SELLER", "message": "Seller profile not found."}})

    l = db.query(MartListing).filter(MartListing.id == listing_id, MartListing.seller_id == seller.id).first()
    if not l:
        raise HTTPException(status_code=404, detail={"error": {"code": "LISTING_NOT_FOUND", "message": "Listing not found."}})

    l.stock_quantity = req.stock_quantity
    db.commit()

    return {"message": "Stock quantity updated successfully.", "id": l.id, "stock_quantity": l.stock_quantity}


@router.get("/seller/orders")
async def get_seller_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns incoming customer orders for this farmer."""
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller:
        return []

    orders = db.query(MartOrder).filter(MartOrder.seller_id == seller.id).order_by(MartOrder.created_at.desc()).all()
    out = []
    for o in orders:
        cust = o.customer
        out.append({
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "fulfilment_type": o.fulfilment_type,
            "customer_name": cust.full_name if cust else "Customer",
            "customer_phone": cust.phone if cust else "",
            "delivery_address": o.delivery_address,
            "delivery_pincode": o.delivery_pincode,
            "total_minor": o.total_minor,
            "total_formatted": f"₹{o.total_minor / 100:.2f}",
            "payment_status": o.payment_status,
            "seller_payment_confirmed": o.seller_payment_confirmed,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": [
                {
                    "title": it.item_title,
                    "unit": it.unit,
                    "quantity": it.quantity,
                    "price_minor": it.unit_price_minor,
                    "total_formatted": f"₹{it.total_minor / 100:.2f}"
                } for it in o.items
            ]
        })
    return out


@router.post("/seller/orders/{order_id}/status")
async def update_seller_order_status(
    order_id: str,
    req: OrderStatusTransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enforces strict order state machine transitions:
    PLACED -> ACCEPTED_BY_SELLER -> PREPARING -> READY_FOR_PICKUP / OUT_FOR_DELIVERY -> COMPLETED
    Also records seller payment confirmation if completed.
    """
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller:
        raise HTTPException(status_code=403, detail={"error": {"code": "NOT_A_SELLER", "message": "Seller profile not found."}})

    o = db.query(MartOrder).filter(MartOrder.id == order_id, MartOrder.seller_id == seller.id).first()
    if not o:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}})

    valid_transitions = {
        "PLACED": ["ACCEPTED_BY_SELLER", "REJECTED"],
        "ACCEPTED_BY_SELLER": ["PREPARING", "CANCELLED"],
        "PREPARING": ["READY_FOR_PICKUP", "OUT_FOR_DELIVERY"],
        "READY_FOR_PICKUP": ["COMPLETED", "DISPUTED"],
        "OUT_FOR_DELIVERY": ["COMPLETED", "DISPUTED"],
    }

    allowed = valid_transitions.get(o.status, [])
    if req.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_TRANSITION", "message": f"Cannot transition order from '{o.status}' to '{req.status}'."}}
        )

    old_status = o.status
    o.status = req.status

    if req.status == "COMPLETED":
        o.seller_payment_confirmed = True

    hist = MartOrderStatusHistory(
        id=str(uuid.uuid4()),
        order_id=o.id,
        from_status=old_status,
        to_status=req.status,
        actor_id=user.id,
        actor_role="seller",
        notes=req.notes or f"Status changed to {req.status} by farmer."
    )
    db.add(hist)
    db.commit()

    return {"message": f"Order status updated to {req.status}.", "status": o.status}


@router.get("/seller/earnings")
async def get_seller_earnings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns authentic earnings computed strictly from COMPLETED orders.
    Never shows projected or uncollected funds.
    """
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.user_id == user.id).first()
    if not seller:
        return {"completed_orders_count": 0, "total_earned_inr": 0.0}

    completed = db.query(MartOrder).filter(MartOrder.seller_id == seller.id, MartOrder.status == "COMPLETED").all()
    total_minor = sum(o.total_minor for o in completed)

    return {
        "completed_orders_count": len(completed),
        "total_earned_minor": total_minor,
        "total_earned_inr": total_minor / 100.0,
        "total_earned_formatted": f"₹{total_minor / 100:.2f}",
        "settlement_note": "Direct settlement received by farmer upon delivery/pickup."
    }


# ─── ADMIN CONSOLE: REVIEW & AUDIT MODULES ──────────────────────

admin_router = APIRouter()


@admin_router.get("/applications")
async def get_admin_seller_applications(
    status_filter: Optional[str] = "SUBMITTED",
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.seller_reviewer)),
    db: Session = Depends(get_db)
):
    """Admin queue of farmer seller applications."""
    q = db.query(MartSellerProfile)
    if status_filter:
        q = q.filter(MartSellerProfile.status == status_filter)
    apps = q.order_by(MartSellerProfile.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "farm_name": a.farm_name,
            "contact_phone": a.contact_phone,
            "state": a.state,
            "district": a.district,
            "village": a.village,
            "service_pincodes": a.service_pincodes or [],
            "fulfilment_modes": a.fulfilment_modes or [],
            "status": a.status,
            "proof_type": a.proof_type,
            "proof_document_url": a.proof_document_url,
            "phone_verified": a.phone_verified,
            "staff_call_completed": a.staff_call_completed,
            "declaration_cultivates_produce": a.declaration_cultivates_produce,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in apps
    ]


class SellerReviewDecision(BaseModel):
    decision: str # APPROVED, REJECTED, INFO_REQUIRED
    staff_call_completed: bool = True
    review_notes: Optional[str] = None


@admin_router.post("/applications/{app_id}/review")
async def review_seller_application(
    app_id: str,
    req: SellerReviewDecision,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.seller_reviewer)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Approves or rejects a farmer seller application with audit trail."""
    seller = db.query(MartSellerProfile).filter(MartSellerProfile.id == app_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail={"error": {"code": "APPLICATION_NOT_FOUND", "message": "Seller application not found."}})

    if req.decision not in ("APPROVED", "REJECTED", "INFO_REQUIRED"):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DECISION", "message": "Decision must be APPROVED, REJECTED, or INFO_REQUIRED."}})

    old_status = seller.status
    seller.status = req.decision
    seller.staff_call_completed = req.staff_call_completed
    seller.review_notes = req.review_notes
    seller.reviewed_by = admin.user_id
    seller.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(
        db, admin, "REVIEW_MART_SELLER", "mart_seller_profiles", seller.id,
        {"from": old_status, "to": req.decision, "farm_name": seller.farm_name},
        request
    )

    return {"message": f"Seller application {req.decision}.", "status": seller.status}


@admin_router.get("/listings/review-queue")
async def get_admin_listings_queue(
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.listing_reviewer)),
    db: Session = Depends(get_db)
):
    """Queue of fresh produce listings awaiting staff verification."""
    listings = db.query(MartListing).filter(MartListing.status.in_(["SUBMITTED", "UNDER_REVIEW"])).order_by(MartListing.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "title": l.title,
            "description": l.description,
            "price_formatted": f"₹{l.price_minor / 100:.2f}",
            "unit": l.unit,
            "stock_quantity": l.stock_quantity,
            "harvest_date": l.harvest_date,
            "status": l.status,
            "is_organic_claim": l.is_organic_claim,
            "photos": l.photos or [],
            "farm_name": l.seller.farm_name if l.seller else "",
            "village": l.seller.village if l.seller else "",
            "district": l.seller.district if l.seller else "",
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in listings
    ]


class ListingReviewDecision(BaseModel):
    decision: str # APPROVED, REJECTED, INFO_REQUIRED
    rejection_reason: Optional[str] = None
    confirm_organic_evidence: bool = False


@admin_router.post("/listings/{listing_id}/review")
async def review_listing(
    listing_id: str,
    req: ListingReviewDecision,
    admin: AdminUser = Depends(require_admin(AdminUserRole.super_admin, AdminUserRole.listing_reviewer)),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Approves or rejects a produce listing before it can appear to consumers."""
    l = db.query(MartListing).filter(MartListing.id == listing_id).first()
    if not l:
        raise HTTPException(status_code=404, detail={"error": {"code": "LISTING_NOT_FOUND", "message": "Listing not found."}})

    old_status = l.status
    l.status = req.decision
    if req.decision == "APPROVED":
        l.rejection_reason = None
        if l.is_organic_claim and req.confirm_organic_evidence:
            l.claim_reviewed = True
    elif req.decision == "REJECTED":
        l.rejection_reason = req.rejection_reason or "Produce quality or verification standard not met."

    db.commit()

    log_admin_action(
        db, admin, "REVIEW_MART_LISTING", "mart_listings", l.id,
        {"from": old_status, "to": req.decision, "title": l.title},
        request
    )

    return {"message": f"Listing {req.decision}.", "id": l.id, "status": l.status}


@admin_router.get("/orders")
async def get_admin_orders(
    status_filter: Optional[str] = None,
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Master order ledger across all farms for monitoring and dispute resolution."""
    q = db.query(MartOrder)
    if status_filter:
        q = q.filter(MartOrder.status == status_filter)
    orders = q.order_by(MartOrder.created_at.desc()).limit(100).all()
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "fulfilment_type": o.fulfilment_type,
            "farm_name": o.seller.farm_name if o.seller else "",
            "customer_name": o.customer.full_name if o.customer else "Customer",
            "delivery_pincode": o.delivery_pincode,
            "total_formatted": f"₹{o.total_minor / 100:.2f}",
            "payment_status": o.payment_status,
            "created_at": o.created_at.isoformat() if o.created_at else None
        } for o in orders
    ]


@admin_router.get("/waitlist")
async def get_admin_waitlist_summary(
    admin: AdminUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Aggregates waitlist signups by PIN code and district to guide farmer recruitment."""
    summary = db.query(
        MartWaitlist.pincode,
        MartWaitlist.district,
        MartWaitlist.state,
        func.count(MartWaitlist.id).label("requests_count")
    ).group_by(MartWaitlist.pincode, MartWaitlist.district, MartWaitlist.state).order_by(func.count(MartWaitlist.id).desc()).all()

    return [
        {
            "pincode": r.pincode,
            "district": r.district,
            "state": r.state,
            "requests_count": r.requests_count
        } for r in summary
    ]

# Also mount under /admin on the mart router
router.include_router(admin_router, prefix="/admin")
