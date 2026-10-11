"""Government Agricultural Schemes & Farmer Profile Eligibility Matching Router.
Provides authentic Central and State Government agricultural subsidies and schemes,
evaluating live farmer profile parameters (State, Land size in acres, Primary crop, Farmer category).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
import uuid
import logging

from ..database.connection import get_db, SessionLocal
from ..database.models import User, GovernmentScheme
from ..auth.deps import get_current_user, get_optional_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── REAL GOVERNMENT SCHEMES DATASET ───────────────────────────────────────
REAL_GOVERNMENT_SCHEMES: List[Dict[str, Any]] = [
    {
        "slug": "pm-kisan",
        "title": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
        "short_description": "Direct income support of ₹6,000 per year directly to bank accounts in three 4-monthly installments.",
        "benefit_summary": "₹6,000 / year Direct Cash Transfer (DBT)",
        "benefit_amount": "₹6,000 / year",
        "category": "Direct Income Support",
        "level": "central",
        "state": None,
        "min_land_acres": 0.0,
        "max_land_acres": None,  # Open to all landholder farmer families
        "eligible_crops": [],    # All crops
        "eligible_farmer_types": ["all", "marginal", "small", "medium"],
        "eligible_states": [],   # All-India
        "application_portal": "https://pmkisan.gov.in",
        "application_process": "Register online on pmkisan.gov.in via 'New Farmer Registration', authenticate with Aadhaar OTP, upload land Pahani/RTC/7-12 record, and link Aadhaar with bank NPCI.",
        "required_documents": [
            "Aadhaar Card linked with active mobile number",
            "Land Record (RTC / Pahani / 7-12 / Khatauni / Khasra)",
            "Aadhaar-seeded Bank Account (NPCI enabled)",
            "Landholding declaration"
        ],
        "key_highlights": [
            "100% centrally funded scheme by Ministry of Agriculture",
            "Transferred directly into bank accounts via DBT without middlemen",
            "Over 11 crore farmers currently supported across India"
        ]
    },
    {
        "slug": "pmfby-crop-insurance",
        "title": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "short_description": "Comprehensive crop insurance shield covering sowing to post-harvest natural risk with ultra-low farmer premiums.",
        "benefit_summary": "Comprehensive Crop Loss Insurance Coverage",
        "benefit_amount": "Up to 100% Sum Insured for Crop Loss",
        "category": "Crop Insurance",
        "level": "central",
        "state": None,
        "min_land_acres": 0.0,
        "max_land_acres": None,
        "eligible_crops": ["Tomato", "Wheat", "Rice / Paddy", "Cotton", "Sugarcane", "Maize", "Onion", "Soybean", "Pulses", "Millets"],
        "eligible_farmer_types": ["all", "marginal", "small", "tenant", "sharecropper"],
        "eligible_states": [],
        "application_portal": "https://pmfby.gov.in",
        "application_process": "Apply online on pmfby.gov.in or through Common Service Centre (CSC) or your local bank branch within 15 days of sowing.",
        "required_documents": [
            "Aadhaar Card",
            "Crop Sowing Certificate / Self-Declaration",
            "Land Record (RTC / 7-12 / Patta)",
            "Bank Passbook copy showing IFSC",
            "Tenant / Sharecropper agreement (if applicable)"
        ],
        "key_highlights": [
            "Max premium only 2% for Kharif crops and 1.5% for Rabi crops",
            "Commercial & horticultural crops capped at 5% farmer premium",
            "Covers localized disasters, mid-season adversity, and post-harvest losses"
        ]
    },
    {
        "slug": "pmksy-per-drop-more-crop",
        "title": "PM Krishi Sinchayee Yojana (PMKSY) — Drip & Sprinkler Subsidy",
        "short_description": "Heavy financial subsidies for installing precision Drip and Sprinkler micro-irrigation systems.",
        "benefit_summary": "Up to 55%–80% Micro-Irrigation Subsidy",
        "benefit_amount": "55% to 80% Cost Subsidy",
        "category": "Micro Irrigation",
        "level": "central",
        "state": None,
        "min_land_acres": 0.5,
        "max_land_acres": None,
        "eligible_crops": ["Tomato", "Sugarcane", "Cotton", "Maize", "Onion", "Horticulture", "Vegetables", "Fruits"],
        "eligible_farmer_types": ["marginal", "small", "all"],
        "eligible_states": [],
        "application_portal": "https://pmksy.gov.in",
        "application_process": "Apply via State Agriculture / Horticulture Department portal or local Assistant Director of Horticulture (ADH) with quotation from empanelled vendor.",
        "required_documents": [
            "Aadhaar Card",
            "Land RTC / 7-12 Extract (showing minimum 0.5 acre)",
            "Water Source Proof (Borewell / Open Well / Canal / River)",
            "Electricity connection certificate / bill",
            "Micro-irrigation equipment quotation from authorized manufacturer"
        ],
        "key_highlights": [
            "55% base central subsidy for Small & Marginal farmers (up to 5 acres)",
            "State top-ups in states like Karnataka, Maharashtra, AP provide up to 75%–90% for SC/ST farmers",
            "Reduces farm water usage by 40-50% while boosting yield by 20-30%"
        ]
    },
    {
        "slug": "kisan-credit-card-miss",
        "title": "Kisan Credit Card (KCC) & 4% Subsidized Crop Loan",
        "short_description": "Low-interest institutional agricultural working capital credit with 3% prompt repayment incentive.",
        "benefit_summary": "Up to ₹3,00,000 Loan at 4% Interest",
        "benefit_amount": "₹1,60,000 Collateral-Free (Up to ₹3 Lakh at 4%)",
        "category": "Agricultural Credit",
        "level": "central",
        "state": None,
        "min_land_acres": 0.0,
        "max_land_acres": None,
        "eligible_crops": [],
        "eligible_farmer_types": ["all", "marginal", "small", "tenant", "dairy", "fisheries"],
        "eligible_states": [],
        "application_portal": "https://www.myscheme.gov.in/schemes/kcc",
        "application_process": "Download one-page KCC form from bank website, attach land record and submit to nearest rural bank branch or via PM-KISAN portal.",
        "required_documents": [
            "KCC Application Form",
            "Aadhaar Card and PAN Card",
            "Land Record (RTC / 7-12 / Khatauni) showing crop cultivated",
            "No Dues Certificate (or self-declaration for loans up to ₹1.6 lakh)"
        ],
        "key_highlights": [
            "Effective interest rate of only 4% per annum upon timely repayment",
            "Collateral-free loan limit up to ₹1.60 lakh",
            "ATM-enabled RuPay Kisan Card for easy cash withdrawal at mandis"
        ]
    },
    {
        "slug": "smam-farm-mechanization",
        "title": "Sub-Mission on Agricultural Mechanization (SMAM)",
        "short_description": "40% to 50% subsidy on purchase of tractors, power tillers, rotavators, sprayers, and combine harvesters.",
        "benefit_summary": "40% to 50% Subsidy on Farm Machinery",
        "benefit_amount": "₹40,000 to ₹2,50,000 Subsidy per machine",
        "category": "Farm Machinery & Mechanization",
        "level": "central",
        "state": None,
        "min_land_acres": 1.0,
        "max_land_acres": None,
        "eligible_crops": [],
        "eligible_farmer_types": ["marginal", "small", "sc", "st", "women", "all"],
        "eligible_states": [],
        "application_portal": "https://agrimachinery.nic.in",
        "application_process": "Register on the DBT in Agriculture Mechanization portal (agrimachinery.nic.in), select machine and empanelled dealer, and upload documents.",
        "required_documents": [
            "Aadhaar Card",
            "Land RTC / 7-12 / Patta (minimum 1 acre)",
            "Bank Passbook copy with IFSC",
            "Caste Certificate (for SC/ST higher subsidy quota)",
            "Vendor Machinery Quotation"
        ],
        "key_highlights": [
            "50% subsidy for Small, Marginal, SC/ST, and Women farmers",
            "40% subsidy for other general category farmers",
            "Up to 80% financial assistance for establishing Custom Hiring Centres (CHC)"
        ]
    },
    {
        "slug": "soil-health-card-scheme",
        "title": "Soil Health Card (SHC) Nutrient Management Scheme",
        "short_description": "100% Free soil testing and personalized fertilizer dosage card provided once every 2 years.",
        "benefit_summary": "Free Soil Testing & Personalized Fertilizer Dosage",
        "benefit_amount": "100% Free Advisory (Saves 15-25% Fertilizer Cost)",
        "category": "Soil Testing & Fertilizer Advisory",
        "level": "central",
        "state": None,
        "min_land_acres": 0.0,
        "max_land_acres": None,
        "eligible_crops": [],
        "eligible_farmer_types": ["all"],
        "eligible_states": [],
        "application_portal": "https://soilhealth.dac.gov.in",
        "application_process": "Contact village Agriculture Assistant or Krishi Vigyan Kendra (KVK). Soil sample collected from field by staff and report issued online.",
        "required_documents": [
            "Aadhaar Card",
            "Farm Survey Number / Gut Number"
        ],
        "key_highlights": [
            "Tests 12 critical parameters: N, P, K, S, Zn, Fe, Cu, Mn, Bo, pH, EC, OC",
            "Prevents excess chemical fertilizer application, reducing farming cost",
            "Digitally downloadable soil health report"
        ]
    },
    {
        "slug": "pkvy-organic-farming",
        "title": "Paramparagat Krishi Vikas Yojana (PKVY)",
        "short_description": "₹50,000 per hectare financial incentive for adopting certified natural and organic farming techniques.",
        "benefit_summary": "₹50,000 / hectare for Organic Inputs & Certification",
        "benefit_amount": "₹50,000 / hectare over 3 years",
        "category": "Organic & Natural Farming",
        "level": "central",
        "state": None,
        "min_land_acres": 1.0,
        "max_land_acres": 5.0,
        "eligible_crops": ["Rice / Paddy", "Wheat", "Millets", "Pulses", "Vegetables", "Cotton"],
        "eligible_farmer_types": ["all", "marginal", "small"],
        "eligible_states": [],
        "application_portal": "https://pgsindia-ncof.gov.in",
        "application_process": "Join or form an organic farming cluster of 20 farmers with nearby holdings and register through local Regional Council or KVK.",
        "required_documents": [
            "Aadhaar Card",
            "Land Record (RTC / 7-12)",
            "Bank Passbook copy",
            "Cluster pledge of non-chemical organic farming"
        ],
        "key_highlights": [
            "₹31,000 per hectare transferred directly for organic inputs (biofertilizers, compost, neem cake)",
            "Free PGS-India organic certification provided",
            "Assistance for value addition and direct organic marketing"
        ]
    },
    {
        "slug": "karnataka-raitha-siri",
        "title": "Karnataka Raitha Siri Scheme (Millet Production Incentive)",
        "short_description": "Direct cash incentive of ₹10,000 per hectare directly to Karnataka farmers growing notified minor millets.",
        "benefit_summary": "₹10,000 / hectare Direct Millet Bonus (Up to ₹20,000)",
        "benefit_amount": "₹10,000 / hectare (Max ₹20,000)",
        "category": "Millet Cultivation Subsidy",
        "level": "state",
        "state": "Karnataka",
        "min_land_acres": 0.5,
        "max_land_acres": 5.0,
        "eligible_crops": ["Millets", "Ragi", "Fox-tail millet / Navane", "Little millet / Same", "Kodo millet / Haraka", "Barnyard millet / Oodalu", "Proso millet / Baragu"],
        "eligible_farmer_types": ["all", "marginal", "small"],
        "eligible_states": ["Karnataka"],
        "application_portal": "https://fruits.karnataka.gov.in",
        "application_process": "Register under Karnataka FRUITS (Farmer Registration and Unified Beneficiary Information System) and declare millet crop in Crop Survey app.",
        "required_documents": [
            "Karnataka FRUITS Farmer ID (FID)",
            "Pahani / RTC showing millet cultivation",
            "Aadhaar Card linked to Bank Account"
        ],
        "key_highlights": [
            "Karnataka State special incentive for nutri-cereals & climate-resilient millets",
            "Direct cash deposit through e-Governance DBT into farmer's bank account",
            "Maximum subsidy up to 2 hectares (₹20,000 per farmer)"
        ]
    },
    {
        "slug": "karnataka-krishi-bhagya",
        "title": "Karnataka Krishi Bhagya Scheme (Farm Pond & Polyhouse Subsidy)",
        "short_description": "80% to 90% subsidy for construction of Farm Ponds (Krishi Honda) with polythene lining and shade net houses.",
        "benefit_summary": "80%–90% Subsidy on Farm Ponds & Water Harvesting",
        "benefit_amount": "Up to ₹1,50,000 for Farm Pond & Polyhouse",
        "category": "Water Harvesting & Farm Ponds",
        "level": "state",
        "state": "Karnataka",
        "min_land_acres": 1.0,
        "max_land_acres": None,
        "eligible_crops": [],
        "eligible_farmer_types": ["marginal", "small", "all"],
        "eligible_states": ["Karnataka"],
        "application_portal": "https://raitamitra.karnataka.gov.in",
        "application_process": "Apply at Raitha Samparka Kendra (RSK) in dryland taluks of Karnataka with RTC and village surveyor sketch.",
        "required_documents": [
            "Land RTC / Pahani",
            "Karnataka FRUITS ID",
            "Caste Certificate (for 90% SC/ST subsidy rate)",
            "Aadhaar Card and Bank Passbook"
        ],
        "key_highlights": [
            "Enables rainfed farmers to save life-saving crops during dry spells",
            "80% subsidy for General category and 90% subsidy for SC/ST farmers",
            "Includes polythene bed lining, fencing, and diesel/solar pump sets"
        ]
    },
    {
        "slug": "maharashtra-namo-shetkari",
        "title": "Maharashtra Namo Shetkari Mahasanman Nidhi Yojana",
        "short_description": "Additional ₹6,000 per year DBT top-up from Maharashtra State Government over and above PM-KISAN.",
        "benefit_summary": "₹6,000 / year Extra State DBT (Total ₹12,000/yr with PM-KISAN)",
        "benefit_amount": "₹6,000 / year",
        "category": "Direct Income Support",
        "level": "state",
        "state": "Maharashtra",
        "min_land_acres": 0.0,
        "max_land_acres": None,
        "eligible_crops": [],
        "eligible_farmer_types": ["all", "marginal", "small"],
        "eligible_states": ["Maharashtra"],
        "application_portal": "https://mahadbt.maharashtra.gov.in",
        "application_process": "Automatic entitlement for all Maharashtra farmers approved under PM-KISAN with active e-KYC and Aadhaar bank linkage.",
        "required_documents": [
            "PM-KISAN Registration ID",
            "Aadhaar Card with biometric e-KYC",
            "7/12 & 8A Land Extract",
            "Bank Account linked with NPCI"
        ],
        "key_highlights": [
            "Delivered in 3 quarterly installments of ₹2,000 each",
            "Combined with PM-KISAN, gives Maharashtra farmers ₹12,000 cash per year",
            "100% paperless direct bank transfer via MahaDBT"
        ]
    },
    {
        "slug": "pm-kmy-pension",
        "title": "Pradhan Mantri Kisan Maandhan Yojana (PM-KMY)",
        "short_description": "Government-backed social security pension scheme providing assured ₹3,000 monthly pension after age 60.",
        "benefit_summary": "₹3,000 / month Assured Pension after 60 years",
        "benefit_amount": "₹3,000 / month (₹36,000 / year)",
        "category": "Social Security & Pension",
        "level": "central",
        "state": None,
        "min_land_acres": 0.0,
        "max_land_acres": 5.0,  # Max 2 hectares (5 acres) Small & Marginal
        "eligible_crops": [],
        "eligible_farmer_types": ["marginal", "small"],
        "eligible_states": [],
        "application_portal": "https://maandhan.in",
        "application_process": "Visit any Village Level CSC (Common Service Centre) or register on maandhan.in with Aadhaar and Savings Bank account.",
        "required_documents": [
            "Aadhaar Card",
            "Savings Bank Account / Jan Dhan Account with IFSC",
            "Land Record (RTC / 7-12) proving land <= 5 acres",
            "Age proof (18 to 40 years at entry)"
        ],
        "key_highlights": [
            "50% matching monthly contribution deposited by Central Government",
            "Low monthly contribution of ₹55 to ₹200 depending on entry age",
            "In case of demise, spouse receives 50% family pension"
        ]
    },
    {
        "slug": "national-beekeeping-honey-mission",
        "title": "National Beekeeping & Honey Mission (NBHM)",
        "short_description": "Up to 80% subsidy for setting up scientific bee colonies and honey harvesting units.",
        "benefit_summary": "Up to 80% Subsidy on Bee Colonies & Honey Equipment",
        "benefit_amount": "Up to ₹1,60,000 for Beekeeping Unit",
        "category": "Allied Agriculture & Beekeeping",
        "level": "central",
        "state": None,
        "min_land_acres": 0.0,
        "max_land_acres": None,
        "eligible_crops": ["Mustard", "Sunflower", "Horticulture", "Fruits", "Vegetables", "Cotton"],
        "eligible_farmer_types": ["marginal", "small", "all"],
        "eligible_states": [],
        "application_portal": "https://nbhm.gov.in",
        "application_process": "Enroll through Madhukranti portal (nbhm.gov.in) with KVK/National Bee Board certification.",
        "required_documents": [
            "Aadhaar Card",
            "Bank Account Details",
            "KVK / Beekeeping Training Certificate (or KVK enrollment)",
            "Land Record (or proof of farm premises)"
        ],
        "key_highlights": [
            "Boosts cross-pollination to increase oilseed and fruit yields by 20-30%",
            "Generates additional annual honey income of ₹40,000–₹80,000",
            "Priority given to women and smallholder self-help groups"
        ]
    }
]


def ensure_schemes_seeded(db: Session):
    """Auto-seeds authentic Indian government schemes if the database is empty."""
    existing_count = db.query(GovernmentScheme).count()
    if existing_count >= len(REAL_GOVERNMENT_SCHEMES):
        return

    for item in REAL_GOVERNMENT_SCHEMES:
        existing = db.query(GovernmentScheme).filter(GovernmentScheme.slug == item["slug"]).first()
        if not existing:
            scheme = GovernmentScheme(
                id=str(uuid.uuid4()),
                slug=item["slug"],
                title=item["title"],
                short_description=item["short_description"],
                benefit_summary=item["benefit_summary"],
                benefit_amount=item.get("benefit_amount"),
                category=item["category"],
                level=item["level"],
                state=item["state"],
                min_land_acres=item["min_land_acres"],
                max_land_acres=item["max_land_acres"],
                eligible_crops=item["eligible_crops"],
                eligible_farmer_types=item["eligible_farmer_types"],
                eligible_states=item["eligible_states"],
                application_portal=item["application_portal"],
                application_process=item["application_process"],
                required_documents=item["required_documents"],
                key_highlights=item["key_highlights"],
                is_active=True
            )
            db.add(scheme)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Error seeding schemes: {e}")


class ProfileCriteria(BaseModel):
    state: Optional[str] = "Karnataka"
    land_acres: Optional[float] = 3.5
    crop: Optional[str] = "Tomato"
    farmer_type: Optional[str] = "small"   # marginal (<=2.5), small (2.5-5), medium (>5)
    category: Optional[str] = "general"    # general, obc, sc, st, women
    irrigation_type: Optional[str] = "borewell" # rainfed, borewell, canal, drip


def evaluate_eligibility(scheme: GovernmentScheme, profile: ProfileCriteria) -> Dict[str, Any]:
    """
    Evaluates farmer eligibility against a government scheme.
    Returns match status ('eligible', 'potentially_eligible', 'conditional'),
    matched criteria list, and tailored explanation.
    """
    p_state = (profile.state or "").strip().lower()
    p_land = float(profile.land_acres if profile.land_acres is not None else 0.0)
    p_crop = (profile.crop or "").strip().lower()
    
    # Automatic farmer scale categorization based on Indian land holding standards
    # Marginal: <= 2.5 acres (1.0 hectare)
    # Small: 2.5 - 5.0 acres (1.0 - 2.0 hectares)
    # Medium/Large: > 5.0 acres
    detected_scale = "marginal" if p_land <= 2.5 else ("small" if p_land <= 5.0 else "medium")

    matched_reasons = []
    unmet_reasons = []
    is_state_match = False
    is_land_match = False
    is_crop_match = False

    # 1. State Criteria
    scheme_states = [s.strip().lower() for s in (scheme.eligible_states or [])]
    if scheme.state:
        scheme_states.append(scheme.state.strip().lower())

    if not scheme_states:
        is_state_match = True
        matched_reasons.append("All-India Central Scheme: Available in all states including " + (profile.state or "your state"))
    elif p_state in scheme_states:
        is_state_match = True
        matched_reasons.append(f"State residency match: You are registered in {profile.state}")
    else:
        unmet_reasons.append(f"Restricted to {scheme.state or 'specific states'}. You selected {profile.state}")

    # 2. Land Size Criteria
    min_l = scheme.min_land_acres if scheme.min_land_acres is not None else 0.0
    max_l = scheme.max_land_acres

    if p_land >= min_l:
        if max_l is None:
            is_land_match = True
            matched_reasons.append(f"Land criteria satisfied: Open to any landholding size (your farm: {p_land} acres)")
        elif p_land <= max_l:
            is_land_match = True
            matched_reasons.append(f"Small/Marginal landholding quota met: Your {p_land} acres is within the {max_l} acre ceiling")
        else:
            unmet_reasons.append(f"Exceeds maximum ceiling of {max_l} acres (your holding: {p_land} acres)")
    else:
        unmet_reasons.append(f"Requires minimum {min_l} acres (your holding: {p_land} acres)")

    # 3. Crop Criteria
    scheme_crops = [c.strip().lower() for c in (scheme.eligible_crops or [])]
    if not scheme_crops:
        is_crop_match = True
        matched_reasons.append(f"Applicable for all crops including your primary crop ({profile.crop or 'general'})")
    else:
        # Check if farmer's crop matches any crop keywords
        matched_crop_name = next((c for c in scheme_crops if c in p_crop or p_crop in c), None)
        if matched_crop_name:
            is_crop_match = True
            matched_reasons.append(f"Notified crop match: {profile.crop} is explicitly eligible for this subsidy")
        else:
            # Check for general crops in PMFBY
            if "tomato" in p_crop or "wheat" in p_crop or "rice" in p_crop or "cotton" in p_crop or "maize" in p_crop or "onion" in p_crop:
                is_crop_match = True
                matched_reasons.append(f"Covered under notified agricultural crops ({profile.crop})")
            else:
                unmet_reasons.append(f"Targeted primarily for: {', '.join(scheme.eligible_crops[:4])}")

    # Determine overall status
    if is_state_match and is_land_match and is_crop_match:
        status_label = "eligible"
        badge = "Eligible"
        score = 95
    elif is_state_match and is_land_match:
        status_label = "potentially_eligible"
        badge = "Potentially Eligible"
        score = 75
    elif is_state_match:
        status_label = "conditional"
        badge = "Conditional"
        score = 50
    else:
        status_label = "not_eligible"
        badge = "Not Eligible"
        score = 20

    return {
        "status": status_label,
        "badge": badge,
        "score": score,
        "farmer_scale": detected_scale,
        "matched_reasons": matched_reasons,
        "unmet_reasons": unmet_reasons,
        "action_advice": "High probability of approval. Gather required documents and submit via official portal." if status_label == "eligible" else ("Review specific crop and criteria before applying." if status_label == "potentially_eligible" else "Check state or category prerequisites.")
    }


# ─── ROUTE ENDPOINTS ────────────────────────────────────────────────────────

@router.get("")
async def list_government_schemes(
    state: Optional[str] = Query(None, description="Filter by state (e.g. Karnataka, Maharashtra)"),
    category: Optional[str] = Query(None, description="Filter by scheme category"),
    level: Optional[str] = Query(None, description="Filter by central or state"),
    db: Session = Depends(get_db)
):
    """
    GET /api/schemes
    Returns all authentic Government agricultural schemes, subsidies, and DBT income programs.
    """
    ensure_schemes_seeded(db)
    query = db.query(GovernmentScheme).filter(GovernmentScheme.is_active == True)

    if level:
        query = query.filter(GovernmentScheme.level == level.lower())
    if category:
        query = query.filter(GovernmentScheme.category.ilike(f"%{category}%"))

    schemes = query.all()

    # If state specified, include Central schemes + that state's schemes
    if state:
        st_clean = state.strip().lower()
        schemes = [
            s for s in schemes
            if s.level == "central" or (s.state and s.state.strip().lower() == st_clean)
        ]

    return [
        {
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "short_description": s.short_description,
            "benefit_summary": s.benefit_summary,
            "benefit_amount": s.benefit_amount,
            "category": s.category,
            "level": s.level,
            "state": s.state,
            "min_land_acres": s.min_land_acres,
            "max_land_acres": s.max_land_acres,
            "eligible_crops": s.eligible_crops or [],
            "application_portal": s.application_portal,
            "required_documents": s.required_documents or [],
            "key_highlights": s.key_highlights or []
        }
        for s in schemes
    ]


@router.get("/my-eligibility")
async def get_my_scheme_eligibility(
    state: Optional[str] = Query("Karnataka"),
    land_acres: Optional[float] = Query(3.5),
    crop: Optional[str] = Query("Tomato"),
    user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/schemes/my-eligibility
    Matches current farmer profile against live government schemes.
    Uses logged-in user profile parameters if present, falling back to query defaults.
    """
    ensure_schemes_seeded(db)
    
    # Use real user profile values if available
    profile_state = state
    profile_land = land_acres
    profile_crop = crop

    if user:
        if getattr(user, "state", None):
            profile_state = user.state
        if getattr(user, "land_size", None) is not None:
            try:
                profile_land = float(user.land_size)
            except Exception:
                pass
        if getattr(user, "crop", None):
            profile_crop = user.crop

    crit = ProfileCriteria(
        state=profile_state,
        land_acres=profile_land,
        crop=profile_crop
    )

    schemes = db.query(GovernmentScheme).filter(GovernmentScheme.is_active == True).all()

    evaluated = []
    eligible_count = 0
    total_estimated_cash_benefit = 0

    for s in schemes:
        eval_res = evaluate_eligibility(s, crit)
        if eval_res["status"] == "eligible":
            eligible_count += 1
            if "6,000" in (s.benefit_amount or ""):
                total_estimated_cash_benefit += 6000
            elif "10,000" in (s.benefit_amount or ""):
                total_estimated_cash_benefit += 10000

        evaluated.append({
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "short_description": s.short_description,
            "benefit_summary": s.benefit_summary,
            "benefit_amount": s.benefit_amount,
            "category": s.category,
            "level": s.level,
            "state": s.state,
            "application_portal": s.application_portal,
            "application_process": s.application_process,
            "required_documents": s.required_documents or [],
            "key_highlights": s.key_highlights or [],
            "eligibility": eval_res
        })

    # Sort: Eligible first, then potentially eligible, then by score descending
    evaluated.sort(key=lambda x: x["eligibility"]["score"], reverse=True)

    return {
        "farmer_profile": {
            "state": crit.state,
            "land_acres": crit.land_acres,
            "crop": crit.crop,
            "scale": "Marginal Farmer (<= 2.5 ac)" if (crit.land_acres or 0) <= 2.5 else ("Small Farmer (2.5-5.0 ac)" if (crit.land_acres or 0) <= 5.0 else "Medium Farmer (> 5.0 ac)")
        },
        "summary": {
            "total_schemes_evaluated": len(evaluated),
            "eligible_schemes_count": eligible_count,
            "estimated_annual_direct_cash_benefit": f"₹{total_estimated_cash_benefit:,}" if total_estimated_cash_benefit else "₹6,000 to ₹16,000+",
            "subsidy_opportunities": "Up to 55%–80% Drip Irrigation + 50% Mechanization + Subsidized 4% KCC Credit"
        },
        "schemes": evaluated
    }


@router.post("/check-eligibility")
async def check_custom_eligibility(
    crit: ProfileCriteria,
    db: Session = Depends(get_db)
):
    """
    POST /api/schemes/check-eligibility
    Accepts customized farmer profile and matches against all government schemes.
    """
    ensure_schemes_seeded(db)
    schemes = db.query(GovernmentScheme).filter(GovernmentScheme.is_active == True).all()

    evaluated = []
    eligible_count = 0
    for s in schemes:
        eval_res = evaluate_eligibility(s, crit)
        if eval_res["status"] == "eligible":
            eligible_count += 1
        evaluated.append({
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "short_description": s.short_description,
            "benefit_summary": s.benefit_summary,
            "benefit_amount": s.benefit_amount,
            "category": s.category,
            "level": s.level,
            "state": s.state,
            "application_portal": s.application_portal,
            "application_process": s.application_process,
            "required_documents": s.required_documents or [],
            "key_highlights": s.key_highlights or [],
            "eligibility": eval_res
        })

    evaluated.sort(key=lambda x: x["eligibility"]["score"], reverse=True)

    return {
        "farmer_profile": {
            "state": crit.state,
            "land_acres": crit.land_acres,
            "crop": crit.crop,
            "scale": "Marginal Farmer (<= 2.5 ac)" if (crit.land_acres or 0) <= 2.5 else ("Small Farmer (2.5-5.0 ac)" if (crit.land_acres or 0) <= 5.0 else "Medium Farmer (> 5.0 ac)")
        },
        "eligible_count": eligible_count,
        "schemes": evaluated
    }


@router.get("/{slug}")
async def get_scheme_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """
    GET /api/schemes/{slug}
    Returns complete details, document checklist, and official application URL for a scheme.
    """
    ensure_schemes_seeded(db)
    s = db.query(GovernmentScheme).filter(GovernmentScheme.slug == slug.lower()).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SCHEME_NOT_FOUND", "message": f"Government scheme '{slug}' not found."}}
        )
    return {
        "id": s.id,
        "slug": s.slug,
        "title": s.title,
        "short_description": s.short_description,
        "benefit_summary": s.benefit_summary,
        "benefit_amount": s.benefit_amount,
        "category": s.category,
        "level": s.level,
        "state": s.state,
        "min_land_acres": s.min_land_acres,
        "max_land_acres": s.max_land_acres,
        "eligible_crops": s.eligible_crops or [],
        "eligible_farmer_types": s.eligible_farmer_types or [],
        "application_portal": s.application_portal,
        "application_process": s.application_process,
        "required_documents": s.required_documents or [],
        "key_highlights": s.key_highlights or [],
        "is_active": s.is_active
    }
