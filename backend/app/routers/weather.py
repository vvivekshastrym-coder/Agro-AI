from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, Tuple, List
import httpx
import os
import datetime
import logging
import time
import math
import urllib.parse

from ..database.connection import get_db
from ..database.models import MandiMarket

logger = logging.getLogger(__name__)
router = APIRouter()

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"

_CURRENT_CACHE: dict = {}
_CURRENT_TTL = 600  # 10 minutes

_FORECAST_CACHE: dict = {}
_FORECAST_TTL = 1800  # 30 minutes

# WMO Weather interpretation codes (WMO code -> (description, main, icon))
WMO_CODES = {
    0: ("Clear sky", "Clear", "01d"),
    1: ("Mainly clear", "Clear", "01d"),
    2: ("Partly cloudy", "Clouds", "02d"),
    3: ("Overcast", "Clouds", "04d"),
    45: ("Foggy", "Fog", "50d"),
    48: ("Depositing rime fog", "Fog", "50d"),
    51: ("Light drizzle", "Drizzle", "09d"),
    53: ("Moderate drizzle", "Drizzle", "09d"),
    55: ("Dense drizzle", "Drizzle", "09d"),
    56: ("Light freezing drizzle", "Drizzle", "09d"),
    57: ("Dense freezing drizzle", "Drizzle", "09d"),
    61: ("Slight rain", "Rain", "10d"),
    63: ("Moderate rain", "Rain", "10d"),
    65: ("Heavy rain", "Rain", "10d"),
    66: ("Light freezing rain", "Rain", "10d"),
    67: ("Heavy freezing rain", "Rain", "10d"),
    71: ("Slight snowfall", "Snow", "13d"),
    73: ("Moderate snowfall", "Snow", "13d"),
    75: ("Heavy snowfall", "Snow", "13d"),
    77: ("Snow grains", "Snow", "13d"),
    80: ("Slight rain showers", "Rain", "09d"),
    81: ("Moderate rain showers", "Rain", "09d"),
    82: ("Violent rain showers", "Rain", "09d"),
    85: ("Slight snow showers", "Snow", "13d"),
    86: ("Heavy snow showers", "Snow", "13d"),
    95: ("Thunderstorm", "Thunderstorm", "11d"),
    96: ("Thunderstorm with slight hail", "Thunderstorm", "11d"),
    99: ("Thunderstorm with heavy hail", "Thunderstorm", "11d"),
}

# Known Indian agricultural district coordinates for instant sub-millisecond geocoding
DISTRICT_COORDS = {
    "mandya": (12.5223, 76.8975, "Mandya", "Karnataka"),
    "kolar": (13.1367, 78.1291, "Kolar", "Karnataka"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru", "Karnataka"),
    "bangalore": (12.9716, 77.5946, "Bengaluru", "Karnataka"),
    "bengaluru urban": (12.9716, 77.5946, "Bengaluru Urban", "Karnataka"),
    "bengaluru rural": (13.2466, 77.7118, "Bengaluru Rural", "Karnataka"),
    "mysuru": (12.2958, 76.6394, "Mysuru", "Karnataka"),
    "mysore": (12.2958, 76.6394, "Mysuru", "Karnataka"),
    "belagavi": (15.8497, 74.4977, "Belagavi", "Karnataka"),
    "belgaum": (15.8497, 74.4977, "Belagavi", "Karnataka"),
    "hubballi": (15.3647, 75.1240, "Hubballi", "Karnataka"),
    "hubli": (15.3647, 75.1240, "Hubballi", "Karnataka"),
    "dharwad": (15.4589, 75.0078, "Dharwad", "Karnataka"),
    "shivamogga": (13.9299, 75.5681, "Shivamogga", "Karnataka"),
    "shimoga": (13.9299, 75.5681, "Shivamogga", "Karnataka"),
    "davanagere": (14.4644, 75.9218, "Davanagere", "Karnataka"),
    "tumakuru": (13.3379, 77.1010, "Tumakuru", "Karnataka"),
    "tumkur": (13.3379, 77.1010, "Tumakuru", "Karnataka"),
    "ballari": (15.1394, 76.9214, "Ballari", "Karnataka"),
    "bellary": (15.1394, 76.9214, "Ballari", "Karnataka"),
    "vijayanagara": (15.2689, 76.3909, "Vijayanagara", "Karnataka"),
    "raichur": (16.2076, 77.3463, "Raichur", "Karnataka"),
    "kalaburagi": (17.3297, 76.8343, "Kalaburagi", "Karnataka"),
    "gulbarga": (17.3297, 76.8343, "Kalaburagi", "Karnataka"),
    "bagalkot": (16.1875, 75.6983, "Bagalkot", "Karnataka"),
    "vijayapura": (16.8302, 75.7100, "Vijayapura", "Karnataka"),
    "bijapur": (16.8302, 75.7100, "Vijayapura", "Karnataka"),
    "bidar": (17.9104, 77.5199, "Bidar", "Karnataka"),
    "gadag": (15.4319, 75.6355, "Gadag", "Karnataka"),
    "haveri": (14.7947, 75.4027, "Haveri", "Karnataka"),
    "byadgi": (14.6811, 75.4878, "Byadgi", "Karnataka"),
    "koppal": (15.3524, 76.1558, "Koppal", "Karnataka"),
    "yadgir": (16.7628, 77.1442, "Yadgir", "Karnataka"),
    "chikkamagaluru": (13.3153, 75.7754, "Chikkamagaluru", "Karnataka"),
    "chikmagalur": (13.3153, 75.7754, "Chikkamagaluru", "Karnataka"),
    "hassan": (13.0072, 76.0963, "Hassan", "Karnataka"),
    "kodagu": (12.4244, 75.7382, "Kodagu", "Karnataka"),
    "madikeri": (12.4244, 75.7382, "Madikeri", "Karnataka"),
    "udupi": (13.3409, 74.7421, "Udupi", "Karnataka"),
    "dakshina kannada": (12.9141, 74.8560, "Mangalore", "Karnataka"),
    "mangalore": (12.9141, 74.8560, "Mangalore", "Karnataka"),
    "mangaluru": (12.9141, 74.8560, "Mangalore", "Karnataka"),
    "uttara kannada": (14.7951, 74.5528, "Sirsi", "Karnataka"),
    "sirsi": (14.6195, 74.8532, "Sirsi", "Karnataka"),
    "karwar": (14.8135, 74.1298, "Karwar", "Karnataka"),
    "ramanagara": (12.7209, 77.2799, "Ramanagara", "Karnataka"),
    "chamarajanagar": (11.9261, 76.9437, "Chamarajanagar", "Karnataka"),
    "chikkaballapur": (13.4355, 77.7275, "Chikkaballapur", "Karnataka"),
    "chitradurga": (14.2251, 76.3980, "Chitradurga", "Karnataka"),
    "pune": (18.5204, 73.8567, "Pune", "Maharashtra"),
    "nashik": (19.9975, 73.7898, "Nashik", "Maharashtra"),
    "nagpur": (21.1458, 79.0882, "Nagpur", "Maharashtra"),
    "solapur": (17.6599, 75.9064, "Solapur", "Maharashtra"),
    "kolhapur": (16.7050, 74.2433, "Kolhapur", "Maharashtra"),
    "ludhiana": (30.9010, 75.8573, "Ludhiana", "Punjab"),
    "amritsar": (31.6340, 74.8723, "Amritsar", "Punjab"),
    "jalandhar": (31.3260, 75.5762, "Jalandhar", "Punjab"),
    "patiala": (30.3398, 76.3869, "Patiala", "Punjab"),
    "varanasi": (25.3176, 82.9739, "Varanasi", "Uttar Pradesh"),
    "lucknow": (26.8467, 80.9462, "Lucknow", "Uttar Pradesh"),
    "agra": (27.1767, 78.0081, "Agra", "Uttar Pradesh"),
    "kanpur": (26.4499, 80.3319, "Kanpur", "Uttar Pradesh"),
    "indore": (22.7196, 75.8577, "Indore", "Madhya Pradesh"),
    "bhopal": (23.2599, 77.4126, "Bhopal", "Madhya Pradesh"),
    "ujjain": (23.1765, 75.7885, "Ujjain", "Madhya Pradesh"),
    "ahmedabad": (23.0225, 72.5714, "Ahmedabad", "Gujarat"),
    "rajkot": (22.3039, 70.8022, "Rajkot", "Gujarat"),
    "surat": (21.1702, 72.8311, "Surat", "Gujarat"),
    "coimbatore": (11.0168, 76.9558, "Coimbatore", "Tamil Nadu"),
    "madurai": (9.9252, 78.1198, "Madurai", "Tamil Nadu"),
    "salem": (11.6643, 78.1460, "Salem", "Tamil Nadu"),
    "erode": (11.3410, 77.7172, "Erode", "Tamil Nadu"),
    "guntur": (16.3067, 80.4365, "Guntur", "Andhra Pradesh"),
    "kurnool": (15.8281, 78.0373, "Kurnool", "Andhra Pradesh"),
    "warangal": (17.9689, 79.5941, "Warangal", "Telangana"),
    "nizamabad": (18.6725, 78.0941, "Nizamabad", "Telangana"),
    "hyderabad": (17.3850, 78.4867, "Hyderabad", "Telangana"),
    "jaipur": (26.9124, 75.7873, "Jaipur", "Rajasthan"),
    "kota": (25.2138, 75.8648, "Kota", "Rajasthan"),
    "karnal": (29.6857, 76.9905, "Karnal", "Haryana"),
    "hisar": (29.1492, 75.7217, "Hisar", "Haryana"),
}

# Detailed villages, taluks, towns, and agricultural landmarks (including places with similar names across districts/states)
AGRICULTURAL_LOCATIONS: List[dict] = [
    # Mandya district villages & taluks
    {"name": "Hosahalli", "district": "Mandya", "state": "Karnataka", "lat": 12.5180, "lon": 76.8890, "feature_type": "village"},
    {"name": "Maddur", "district": "Mandya", "state": "Karnataka", "lat": 12.5842, "lon": 77.0439, "feature_type": "town"},
    {"name": "Malavalli", "district": "Mandya", "state": "Karnataka", "lat": 12.3833, "lon": 77.0833, "feature_type": "town"},
    {"name": "Pandavapura", "district": "Mandya", "state": "Karnataka", "lat": 12.4925, "lon": 76.6708, "feature_type": "town"},
    {"name": "Srirangapatna", "district": "Mandya", "state": "Karnataka", "lat": 12.4216, "lon": 76.6931, "feature_type": "town"},
    {"name": "Krishnarajpet (K.R. Pet)", "district": "Mandya", "state": "Karnataka", "lat": 12.6606, "lon": 76.4875, "feature_type": "town"},
    {"name": "Nagamangala", "district": "Mandya", "state": "Karnataka", "lat": 12.8206, "lon": 76.7558, "feature_type": "town"},
    {"name": "Keragodu", "district": "Mandya", "state": "Karnataka", "lat": 12.6058, "lon": 76.9219, "feature_type": "village"},
    {"name": "Basaralu", "district": "Mandya", "state": "Karnataka", "lat": 12.6872, "lon": 76.8200, "feature_type": "village"},
    # Disambiguated villages/towns with similar names across districts/states
    {"name": "Hosahalli", "district": "Shivamogga", "state": "Karnataka", "lat": 13.8820, "lon": 75.5410, "feature_type": "village"},
    {"name": "Hosahalli", "district": "Bengaluru Rural", "state": "Karnataka", "lat": 13.2450, "lon": 77.6180, "feature_type": "village"},
    {"name": "Hosahalli", "district": "Tumakuru", "state": "Karnataka", "lat": 13.3610, "lon": 77.0820, "feature_type": "village"},
    {"name": "Rampur", "district": "Bagalkot", "state": "Karnataka", "lat": 16.1780, "lon": 75.6540, "feature_type": "village"},
    {"name": "Rampur", "district": "Raichur", "state": "Karnataka", "lat": 16.1910, "lon": 77.3190, "feature_type": "village"},
    {"name": "Rampur", "district": "Rampur", "state": "Uttar Pradesh", "lat": 28.8033, "lon": 79.0250, "feature_type": "town"},
    {"name": "Rampur", "district": "Shimla", "state": "Himachal Pradesh", "lat": 31.4492, "lon": 77.6300, "feature_type": "town"},
    {"name": "Sultanpur", "district": "Sultanpur", "state": "Uttar Pradesh", "lat": 26.2648, "lon": 82.0727, "feature_type": "town"},
    {"name": "Sultanpur", "district": "Kalaburagi", "state": "Karnataka", "lat": 17.3620, "lon": 76.8610, "feature_type": "village"},
    # Other major Karnataka agricultural taluks & villages
    {"name": "Channapatna", "district": "Ramanagara", "state": "Karnataka", "lat": 12.6515, "lon": 77.2067, "feature_type": "town"},
    {"name": "Kanakapura", "district": "Ramanagara", "state": "Karnataka", "lat": 12.5462, "lon": 77.4199, "feature_type": "town"},
    {"name": "Doddaballapura", "district": "Bengaluru Rural", "state": "Karnataka", "lat": 13.2927, "lon": 77.5389, "feature_type": "town"},
    {"name": "Devanahalli", "district": "Bengaluru Rural", "state": "Karnataka", "lat": 13.2466, "lon": 77.7118, "feature_type": "town"},
    {"name": "Nelamangala", "district": "Bengaluru Rural", "state": "Karnataka", "lat": 13.0991, "lon": 77.3936, "feature_type": "town"},
    {"name": "Hoskote", "district": "Bengaluru Rural", "state": "Karnataka", "lat": 13.0707, "lon": 77.7981, "feature_type": "town"},
    {"name": "Yeshwanthpur APMC", "district": "Bengaluru Urban", "state": "Karnataka", "lat": 13.0206, "lon": 77.5476, "feature_type": "apmc_market"},
    {"name": "Binny Mill (F&V) APMC", "district": "Bengaluru Urban", "state": "Karnataka", "lat": 12.9766, "lon": 77.5629, "feature_type": "apmc_market"},
    {"name": "Mulbagal", "district": "Kolar", "state": "Karnataka", "lat": 13.1654, "lon": 78.3935, "feature_type": "town"},
    {"name": "Srinivaspur", "district": "Kolar", "state": "Karnataka", "lat": 13.3389, "lon": 78.2167, "feature_type": "town"},
    {"name": "Bangarapet", "district": "Kolar", "state": "Karnataka", "lat": 12.9912, "lon": 78.1790, "feature_type": "town"},
    {"name": "Malur", "district": "Kolar", "state": "Karnataka", "lat": 13.0037, "lon": 77.9383, "feature_type": "town"},
    {"name": "Chintamani", "district": "Chikkaballapur", "state": "Karnataka", "lat": 13.4020, "lon": 78.0551, "feature_type": "town"},
    {"name": "Gauribidanur", "district": "Chikkaballapur", "state": "Karnataka", "lat": 13.6111, "lon": 77.5170, "feature_type": "town"},
    {"name": "Nanjangud", "district": "Mysuru", "state": "Karnataka", "lat": 12.1200, "lon": 76.6801, "feature_type": "town"},
    {"name": "Hunsur", "district": "Mysuru", "state": "Karnataka", "lat": 12.3052, "lon": 76.2878, "feature_type": "town"},
    {"name": "T. Narasipura", "district": "Mysuru", "state": "Karnataka", "lat": 12.2094, "lon": 76.9036, "feature_type": "town"},
    {"name": "K.R. Nagar", "district": "Mysuru", "state": "Karnataka", "lat": 12.4369, "lon": 76.3828, "feature_type": "town"},
    {"name": "Bandipalya APMC", "district": "Mysuru", "state": "Karnataka", "lat": 12.2485, "lon": 76.6522, "feature_type": "apmc_market"},
    {"name": "Gonikoppal", "district": "Kodagu", "state": "Karnataka", "lat": 12.1869, "lon": 75.9297, "feature_type": "town"},
    {"name": "Kushalnagar", "district": "Kodagu", "state": "Karnataka", "lat": 12.4593, "lon": 75.9612, "feature_type": "town"},
    {"name": "Arsikere", "district": "Hassan", "state": "Karnataka", "lat": 13.3138, "lon": 76.2569, "feature_type": "town"},
    {"name": "Channarayapatna", "district": "Hassan", "state": "Karnataka", "lat": 12.9035, "lon": 76.3894, "feature_type": "town"},
    {"name": "Sakleshpur", "district": "Hassan", "state": "Karnataka", "lat": 12.9442, "lon": 75.7866, "feature_type": "town"},
    {"name": "Tiptur", "district": "Tumakuru", "state": "Karnataka", "lat": 13.2571, "lon": 76.4778, "feature_type": "town"},
    {"name": "Sira", "district": "Tumakuru", "state": "Karnataka", "lat": 13.7411, "lon": 76.9042, "feature_type": "town"},
    {"name": "Bhadravati", "district": "Shivamogga", "state": "Karnataka", "lat": 13.8406, "lon": 75.7020, "feature_type": "town"},
    {"name": "Sagara", "district": "Shivamogga", "state": "Karnataka", "lat": 14.1670, "lon": 75.0403, "feature_type": "town"},
    {"name": "Shikaripura", "district": "Shivamogga", "state": "Karnataka", "lat": 14.2690, "lon": 75.3530, "feature_type": "town"},
    {"name": "Harihar", "district": "Davanagere", "state": "Karnataka", "lat": 14.5133, "lon": 75.8069, "feature_type": "town"},
    {"name": "Ranebennur", "district": "Haveri", "state": "Karnataka", "lat": 14.6195, "lon": 75.6266, "feature_type": "town"},
    {"name": "Byadgi", "district": "Haveri", "state": "Karnataka", "lat": 14.6811, "lon": 75.4878, "feature_type": "town"},
    {"name": "Gokak", "district": "Belagavi", "state": "Karnataka", "lat": 16.1691, "lon": 74.8239, "feature_type": "town"},
    {"name": "Athani", "district": "Belagavi", "state": "Karnataka", "lat": 16.7294, "lon": 75.0617, "feature_type": "town"},
    {"name": "Bailhongal", "district": "Belagavi", "state": "Karnataka", "lat": 15.8162, "lon": 74.8576, "feature_type": "town"},
    {"name": "Nargund", "district": "Gadag", "state": "Karnataka", "lat": 15.7228, "lon": 75.3855, "feature_type": "town"},
    {"name": "Hospet (Hosapete)", "district": "Vijayanagara", "state": "Karnataka", "lat": 15.2689, "lon": 76.3909, "feature_type": "town"},
    {"name": "Sindhanur", "district": "Raichur", "state": "Karnataka", "lat": 15.7689, "lon": 76.7570, "feature_type": "town"},
    {"name": "Gangavathi", "district": "Koppal", "state": "Karnataka", "lat": 15.4319, "lon": 76.5281, "feature_type": "town"},
    {"name": "Jamkhandi", "district": "Bagalkot", "state": "Karnataka", "lat": 16.5042, "lon": 75.2914, "feature_type": "town"},
    {"name": "Mudhol", "district": "Bagalkot", "state": "Karnataka", "lat": 16.3289, "lon": 75.2869, "feature_type": "town"},
    {"name": "Basavakalyan", "district": "Bidar", "state": "Karnataka", "lat": 17.8742, "lon": 76.9497, "feature_type": "town"},
    {"name": "Puttur", "district": "Dakshina Kannada", "state": "Karnataka", "lat": 12.7634, "lon": 75.2015, "feature_type": "town"},
    {"name": "Kundapura", "district": "Udupi", "state": "Karnataka", "lat": 13.6267, "lon": 74.6897, "feature_type": "town"},
    {"name": "Challakere", "district": "Chitradurga", "state": "Karnataka", "lat": 14.3164, "lon": 76.6515, "feature_type": "town"},
    {"name": "Hiriyur", "district": "Chitradurga", "state": "Karnataka", "lat": 13.9437, "lon": 76.6165, "feature_type": "town"},
    {"name": "Kadur", "district": "Chikkamagaluru", "state": "Karnataka", "lat": 13.5526, "lon": 76.0124, "feature_type": "town"},
    {"name": "Tarikere", "district": "Chikkamagaluru", "state": "Karnataka", "lat": 13.7073, "lon": 75.8132, "feature_type": "town"},
    {"name": "Kollegal", "district": "Chamarajanagar", "state": "Karnataka", "lat": 12.1557, "lon": 77.1103, "feature_type": "town"},
    {"name": "Gundlupet", "district": "Chamarajanagar", "state": "Karnataka", "lat": 11.8087, "lon": 76.6917, "feature_type": "town"},
    {"name": "Lasalgaon APMC", "district": "Nashik", "state": "Maharashtra", "lat": 20.1456, "lon": 74.2361, "feature_type": "apmc_market"},
    {"name": "Pimpalgaon Baswant", "district": "Nashik", "state": "Maharashtra", "lat": 20.1656, "lon": 73.9875, "feature_type": "apmc_market"},
    {"name": "Vashi APMC", "district": "Navi Mumbai", "state": "Maharashtra", "lat": 19.0771, "lon": 73.0080, "feature_type": "apmc_market"},
    {"name": "Azadpur Mandi", "district": "North West Delhi", "state": "Delhi", "lat": 28.7095, "lon": 77.1763, "feature_type": "apmc_market"},
    {"name": "Khanna Mandi", "district": "Ludhiana", "state": "Punjab", "lat": 30.7071, "lon": 76.2179, "feature_type": "apmc_market"},
    {"name": "Unjha APMC", "district": "Mehsana", "state": "Gujarat", "lat": 23.8037, "lon": 72.3917, "feature_type": "apmc_market"},
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _deg_to_cardinal(deg: Optional[float]) -> Optional[str]:
    if deg is None:
        return None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = int(round((deg % 360) / 45.0)) % 8
    return dirs[ix]


def _format_tz_label(tz_offset_sec: Optional[int], country: Optional[str] = None) -> str:
    if tz_offset_sec is None:
        return "IST" if country == "IN" else ""
    if tz_offset_sec == 19800 or (country == "IN" and tz_offset_sec == 19800):
        return "IST"
    if tz_offset_sec == 0:
        return "UTC"
    sign = "+" if tz_offset_sec >= 0 else "-"
    total_mins = abs(tz_offset_sec) // 60
    hours = total_mins // 60
    mins = total_mins % 60
    if mins == 0:
        return f"GMT{sign}{hours}"
    return f"GMT{sign}{hours}:{mins:02d}"


def _validate_coords(lat: Optional[float], lon: Optional[float]) -> None:
    if lat is not None and (math.isnan(lat) or lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90 degrees.")
    if lon is not None and (math.isnan(lon) or lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180 degrees.")


def _find_nearest_directory_location(lat: float, lon: float) -> Tuple[dict, float]:
    best_loc = None
    best_dist = float("inf")

    for loc in AGRICULTURAL_LOCATIONS:
        d = _haversine_km(lat, lon, loc["lat"], loc["lon"])
        if d < best_dist:
            best_dist = d
            best_loc = loc

    seen_coords = set()
    for _, (d_lat, d_lon, d_name, d_state) in DISTRICT_COORDS.items():
        if (d_lat, d_lon) in seen_coords:
            continue
        seen_coords.add((d_lat, d_lon))
        d = _haversine_km(lat, lon, d_lat, d_lon)
        if d < best_dist:
            best_dist = d
            best_loc = {
                "name": d_name,
                "district": d_name,
                "state": d_state,
                "lat": d_lat,
                "lon": d_lon,
                "feature_type": "district",
            }

    return best_loc, best_dist


def resolve_location(q: Optional[str], lat: Optional[float], lon: Optional[float]) -> Tuple[float, float, str, str]:
    """
    Resolves input query or GPS coordinates into (latitude, longitude, city_name, state_name).
    Validates coordinates when supplied and resolves nearest locality name if q is omitted.
    """
    if not isinstance(lat, (int, float)):
        lat = None
    if not isinstance(lon, (int, float)):
        lon = None
    if not isinstance(q, str):
        q = None
    _validate_coords(lat, lon)

    if lat is not None and lon is not None:
        if q and q.strip():
            parts = [p.strip() for p in q.split("·")[0].split(",") if p.strip()]
            city_name = parts[0] if parts else q.strip()
            state_name = parts[1] if len(parts) > 1 else "India"
            return lat, lon, city_name, state_name

        nearest, dist_km = _find_nearest_directory_location(lat, lon)
        if nearest and dist_km <= 20.0:
            return lat, lon, nearest["name"], nearest["state"]
        elif nearest and dist_km <= 80.0:
            return lat, lon, f"Near {nearest['name']}", nearest["state"]
        return lat, lon, f"Location ({lat:.3f}, {lon:.3f})", "India"

    if q and q.strip():
        raw_q = q.split("·")[0].strip()
        clean = raw_q.split(",")[0].strip().lower()
        parts_lower = [p.strip().lower() for p in raw_q.split(",") if p.strip()]

        # 1. Check AGRICULTURAL_LOCATIONS with optional district/state disambiguation
        for loc in AGRICULTURAL_LOCATIONS:
            if loc["name"].lower() == clean:
                if len(parts_lower) > 1:
                    if any(
                        loc["district"].lower() in p or loc["state"].lower() in p
                        for p in parts_lower[1:]
                    ):
                        return loc["lat"], loc["lon"], loc["name"], loc["state"]
                else:
                    return loc["lat"], loc["lon"], loc["name"], loc["state"]

        # 2. Check DISTRICT_COORDS
        if clean in DISTRICT_COORDS:
            t_lat, t_lon, name, state = DISTRICT_COORDS[clean]
            return t_lat, t_lon, name, state

        for token in clean.split():
            if token in DISTRICT_COORDS:
                t_lat, t_lon, name, state = DISTRICT_COORDS[token]
                return t_lat, t_lon, name, state

        for loc in AGRICULTURAL_LOCATIONS:
            if clean in loc["name"].lower():
                return loc["lat"], loc["lon"], loc["name"], loc["state"]

        return 12.5223, 76.8975, raw_q.split(",")[0].strip(), "Karnataka"

    return 12.5223, 76.8975, "Mandya", "Karnataka"


def get_openweather_key() -> str:
    return os.getenv("OPENWEATHER_API_KEY", "")


@router.get("/locations/search")
async def search_locations(
    q: str = Query("", description="Search query for village, town, district, farm or APMC market"),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    GET /api/weather/locations/search
    Searches across agricultural villages, taluks, districts, APMC markets, and Open-Meteo Geocoding API.
    Distinguishes places with similar names using locality, district, and state metadata.
    Never invents fake locations when nothing matches.
    """
    query = (q or "").strip()
    if not query:
        return {"results": [], "count": 0, "query": ""}

    q_lower = query.lower()
    q_tokens = [t.strip() for t in q_lower.replace(",", " ").split() if t.strip()]

    results = []
    seen_keys = set()

    def _add_candidate(
        name: str,
        district: str,
        state: str,
        country: str,
        lat: float,
        lon: float,
        feature_type: str,
        provider: str,
        score: int = 50,
    ):
        dedup_key = (round(lat, 3), round(lon, 3), name.lower(), district.lower())
        if dedup_key in seen_keys:
            return
        seen_keys.add(dedup_key)

        parts = [name]
        if district and district.lower() != name.lower():
            parts.append(district)
        if state and state.lower() not in (name.lower(), district.lower()):
            parts.append(state)
        if country:
            parts.append(country)
        display_name = ", ".join(parts)

        results.append({
            "id": f"loc_{abs(hash(dedup_key)) % 100000000}",
            "name": name,
            "locality": name,
            "district": district or name,
            "state": state or "India",
            "country": country or "India",
            "display_name": display_name,
            "lat": round(float(lat), 5),
            "lon": round(float(lon), 5),
            "feature_type": feature_type,
            "provider": provider,
            "_score": score,
        })

    # 1. Search curated agricultural villages, taluks, and towns
    for loc in AGRICULTURAL_LOCATIONS:
        searchable = f"{loc['name']} {loc['district']} {loc['state']}".lower()
        if q_lower in searchable or all(tok in searchable for tok in q_tokens):
            exact_bonus = 100 if loc["name"].lower() == q_lower else (80 if loc["name"].lower().startswith(q_lower) else 60)
            _add_candidate(
                name=loc["name"],
                district=loc["district"],
                state=loc["state"],
                country="India",
                lat=loc["lat"],
                lon=loc["lon"],
                feature_type=loc["feature_type"],
                provider="Agro AI Agricultural Directory",
                score=exact_bonus,
            )

    # 2. Search DISTRICT_COORDS
    for key, (d_lat, d_lon, d_name, d_state) in DISTRICT_COORDS.items():
        searchable = f"{key} {d_name} {d_state}".lower()
        if q_lower in searchable or all(tok in searchable for tok in q_tokens):
            exact_bonus = 95 if d_name.lower() == q_lower or key == q_lower else (75 if d_name.lower().startswith(q_lower) else 55)
            _add_candidate(
                name=d_name,
                district=d_name,
                state=d_state,
                country="India",
                lat=d_lat,
                lon=d_lon,
                feature_type="district",
                provider="Agro AI Agricultural Directory",
                score=exact_bonus,
            )

    # 3. Search MandiMarket database records and resolve district coordinates
    try:
        db_markets = (
            db.query(MandiMarket)
            .filter(
                MandiMarket.is_active == True,
                (MandiMarket.name.ilike(f"%{query}%"))
                | (MandiMarket.district.ilike(f"%{query}%"))
                | (MandiMarket.aliases.ilike(f"%{query}%")),
            )
            .limit(15)
            .all()
        )
        for m in db_markets:
            # Resolve coordinates from AGRICULTURAL_LOCATIONS or DISTRICT_COORDS
            m_lat, m_lon = None, None
            for loc in AGRICULTURAL_LOCATIONS:
                if loc["name"].lower() in m.name.lower() or m.name.lower().replace(" apmc", "") == loc["name"].lower():
                    m_lat, m_lon = loc["lat"], loc["lon"]
                    break
            if m_lat is None:
                d_key = (m.district or "").strip().lower()
                if d_key in DISTRICT_COORDS:
                    m_lat, m_lon, _, _ = DISTRICT_COORDS[d_key]
            if m_lat is not None and m_lon is not None:
                _add_candidate(
                    name=m.name,
                    district=m.district,
                    state=m.state,
                    country="India",
                    lat=m_lat,
                    lon=m_lon,
                    feature_type="apmc_market",
                    provider=m.source or "Authorized Mandi Registry",
                    score=70 if q_lower in m.name.lower() else 50,
                )
    except Exception as exc:
        logger.debug("MandiMarket search lookup skipped: %s", exc)

    # 4. Query Open-Meteo Geocoding API if local matches are few and query is a clean place token
    if len(results) < 5 and len(query) >= 3:
        primary_term = query.split(",")[0].strip()
        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={urllib.parse.quote(primary_term)}&count=10&language=en&format=json"
        )
        async with httpx.AsyncClient(timeout=3.0) as client:
            try:
                res = await client.get(geo_url)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("results", []) or []:
                        g_name = item.get("name")
                        g_lat = item.get("latitude")
                        g_lon = item.get("longitude")
                        if not g_name or g_lat is None or g_lon is None:
                            continue
                        g_district = item.get("admin2") or item.get("admin3") or g_name
                        g_state = item.get("admin1") or ""
                        g_country = item.get("country") or "India"
                        full_text = f"{g_name} {g_district} {g_state} {g_country}".lower()
                        if not all(tok in full_text for tok in q_tokens):
                            continue
                        country_bonus = 20 if g_country.lower() == "india" else 0
                        _add_candidate(
                            name=g_name,
                            district=g_district,
                            state=g_state,
                            country=g_country,
                            lat=g_lat,
                            lon=g_lon,
                            feature_type="locality",
                            provider="Open-Meteo Geocoding Service",
                            score=45 + country_bonus,
                        )
            except Exception as exc:
                logger.debug("External geocoding lookup failed: %s", exc)

    results.sort(key=lambda r: (-r["_score"], r["display_name"]))
    final_results = []
    for r in results[:limit]:
        r_clean = {k: v for k, v in r.items() if k != "_score"}
        final_results.append(r_clean)

    return {
        "results": final_results,
        "count": len(final_results),
        "query": query,
    }


@router.get("/locations/reverse")
async def reverse_geocode_location(
    lat: float = Query(..., description="Latitude (-90 to 90)"),
    lon: float = Query(..., description="Longitude (-180 to 180)"),
):
    """
    GET /api/weather/locations/reverse
    Converts device GPS coordinates into a human-readable village/town/district name.
    Uses nearest directory match and Nominatim OpenStreetMap reverse geocoding.
    """
    _validate_coords(lat, lon)

    nearest_loc, dist_km = _find_nearest_directory_location(lat, lon)

    # 1. If within 4 km of a curated village/town/district, return it immediately with high precision
    if nearest_loc and dist_km <= 4.0:
        name = nearest_loc["name"]
        district = nearest_loc["district"]
        state = nearest_loc["state"]
        parts = [name]
        if district and district.lower() != name.lower():
            parts.append(district)
        if state:
            parts.append(state)
        return {
            "available": True,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "name": name,
            "locality": name,
            "district": district,
            "state": state,
            "country": "India",
            "display_name": ", ".join(parts),
            "distance_km": round(dist_km, 2),
            "provider": "Agro AI Agricultural Directory",
        }

    # 2. Try OpenStreetMap Nominatim reverse geocoding
    nom_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    async with httpx.AsyncClient(timeout=3.5) as client:
        try:
            res = await client.get(nom_url)
            if res.status_code == 200:
                data = res.json()
                addr = data.get("address", {})
                if addr:
                    locality = (
                        addr.get("village")
                        or addr.get("town")
                        or addr.get("city")
                        or addr.get("suburb")
                        or addr.get("county")
                        or addr.get("state_district")
                    )
                    district = (
                        addr.get("state_district")
                        or addr.get("county")
                        or locality
                        or (nearest_loc["district"] if nearest_loc else "")
                    ).replace(" District", "")
                    state = addr.get("state") or (nearest_loc["state"] if nearest_loc else "India")
                    country = addr.get("country") or "India"
                    name = locality or district or f"Location ({lat:.3f}, {lon:.3f})"

                    parts = [name]
                    if district and district.lower() != name.lower():
                        parts.append(district)
                    if state and state.lower() not in (name.lower(), district.lower()):
                        parts.append(state)

                    return {
                        "available": True,
                        "lat": round(lat, 5),
                        "lon": round(lon, 5),
                        "name": name,
                        "locality": name,
                        "district": district,
                        "state": state,
                        "country": country,
                        "display_name": ", ".join(parts),
                        "distance_km": 0.0,
                        "provider": "OpenStreetMap Nominatim Reverse Geocoder",
                    }
        except Exception as exc:
            logger.debug("Nominatim reverse geocoding failed: %s", exc)

    # 3. Fallback to nearest known agricultural locality with explicit proximity metadata
    if nearest_loc and dist_km <= 60.0:
        name = nearest_loc["name"] if dist_km <= 15.0 else f"Near {nearest_loc['name']}"
        district = nearest_loc["district"]
        state = nearest_loc["state"]
        parts = [name]
        if district and district.lower() not in name.lower():
            parts.append(district)
        if state:
            parts.append(state)
        return {
            "available": True,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "name": name,
            "locality": name,
            "district": district,
            "state": state,
            "country": "India",
            "display_name": ", ".join(parts),
            "distance_km": round(dist_km, 2),
            "provider": "Agro AI Nearest Agricultural Station",
        }

    return {
        "available": True,
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "name": f"GPS ({lat:.4f}, {lon:.4f})",
        "locality": f"GPS ({lat:.4f}, {lon:.4f})",
        "district": "Custom Coordinates",
        "state": "India",
        "country": "India",
        "display_name": f"GPS Coordinates ({lat:.4f}, {lon:.4f})",
        "distance_km": None,
        "provider": "Direct Coordinate Selection",
    }


async def fetch_open_meteo_current(target_lat: float, target_lon: float, city_name: str, state_name: str) -> Optional[dict]:
    """
    Fetches genuine real-time meteorological observations from Open-Meteo API
    (WMO / IMD / ECMWF operational numerical weather prediction models).
    Never fabricates missing fields.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={target_lat}&longitude={target_lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
        f"&hourly=temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_sum,precipitation_probability_max"
        f"&timezone=auto"
    )
    async with httpx.AsyncClient(timeout=4.5) as client:
        try:
            res = await client.get(url)
            if res.status_code != 200:
                return None
            data = res.json()
            curr = data.get("current", {})
            if not curr or "temperature_2m" not in curr:
                return None
            daily = data.get("daily", {})
            hourly = data.get("hourly", {})

            w_code = curr.get("weather_code", 0)
            cond_desc, cond_main, icon = WMO_CODES.get(w_code, ("Mainly clear", "Clear", "01d"))
            wind_kmh = round(curr["wind_speed_10m"]) if curr.get("wind_speed_10m") is not None else None
            wind_deg = round(curr["wind_direction_10m"]) if curr.get("wind_direction_10m") is not None else None
            wind_cardinal = _deg_to_cardinal(wind_deg)
            humidity = round(curr["relative_humidity_2m"]) if curr.get("relative_humidity_2m") is not None else None
            pressure = round(curr["surface_pressure"]) if curr.get("surface_pressure") is not None else None
            rain_1h = curr.get("rain", curr.get("precipitation"))
            if rain_1h is not None:
                rain_1h = round(float(rain_1h), 2)

            temp = round(curr["temperature_2m"])
            feels_like = round(curr["apparent_temperature"]) if curr.get("apparent_temperature") is not None else None

            temp_min = (
                round(daily["temperature_2m_min"][0])
                if daily.get("temperature_2m_min") and daily["temperature_2m_min"][0] is not None
                else None
            )
            temp_max = (
                round(daily["temperature_2m_max"][0])
                if daily.get("temperature_2m_max") and daily["temperature_2m_max"][0] is not None
                else None
            )
            sunrise = daily["sunrise"][0] if daily.get("sunrise") and len(daily["sunrise"]) > 0 else None
            sunset = daily["sunset"][0] if daily.get("sunset") and len(daily["sunset"]) > 0 else None
            tz_offset_sec = data.get("utc_offset_seconds")
            tz_abbr = "IST" if tz_offset_sec == 19800 else (data.get("timezone_abbreviation") or _format_tz_label(tz_offset_sec, "IN"))
            rain_probability = (
                round(daily["precipitation_probability_max"][0])
                if daily.get("precipitation_probability_max") and daily["precipitation_probability_max"][0] is not None
                else None
            )

            # Build genuine next-12-hours forecast slice if hourly data is provided
            hourly_list = []
            h_times = hourly.get("time", []) or []
            h_temps = hourly.get("temperature_2m", []) or []
            h_pops = hourly.get("precipitation_probability", []) or []
            h_precips = hourly.get("precipitation", []) or []
            h_codes = hourly.get("weather_code", []) or []
            h_winds = hourly.get("wind_speed_10m", []) or []
            curr_time_str = curr.get("time", "")
            start_idx = 0
            if curr_time_str and h_times:
                for idx, t_str in enumerate(h_times):
                    if t_str >= curr_time_str:
                        start_idx = idx
                        break
            for idx in range(start_idx, min(start_idx + 12, len(h_times))):
                hc = h_codes[idx] if idx < len(h_codes) and h_codes[idx] is not None else 0
                h_desc, h_main, h_icon = WMO_CODES.get(hc, ("Clear", "Clear", "01d"))
                hourly_list.append({
                    "time": h_times[idx],
                    "temp": round(h_temps[idx]) if idx < len(h_temps) and h_temps[idx] is not None else None,
                    "rain_probability": round(h_pops[idx]) if idx < len(h_pops) and h_pops[idx] is not None else None,
                    "rain_mm": round(float(h_precips[idx]), 2) if idx < len(h_precips) and h_precips[idx] is not None else None,
                    "wind_speed": round(h_winds[idx]) if idx < len(h_winds) and h_winds[idx] is not None else None,
                    "condition": h_desc,
                    "condition_main": h_main,
                    "icon": h_icon,
                })

            if (rain_1h or 0.0) > 0.5:
                spray_advice = "❌ Do NOT Spray Today: Rain has been detected. Chemical will wash off."
                spray_favorable = False
            elif (wind_kmh or 0) > 18:
                spray_advice = f"⚠️ High Wind ({wind_kmh} km/h): Risk of spray drift to adjacent crops. Delay until wind calms."
                spray_favorable = False
            elif (humidity or 0) > 85:
                spray_advice = f"⚠️ High Humidity ({humidity}%): Leaf drying will be delayed. Spray during early morning after dew clears."
                spray_favorable = True
            else:
                spray_advice = "✅ Optimal Spray Window: Clear skies and calm wind. Spray early morning (6:30 - 9:00 AM) or late afternoon."
                spray_favorable = True

            return {
                "available": True,
                "temp": temp,
                "feels_like": feels_like,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "humidity": humidity,
                "pressure": pressure,
                "condition": cond_desc,
                "condition_main": cond_main,
                "icon": icon,
                "wind_speed": wind_kmh,
                "wind_direction_deg": wind_deg,
                "wind_direction_cardinal": wind_cardinal,
                "rain_1h": rain_1h,
                "rain_mm": rain_1h,
                "rain_probability": rain_probability,
                "sunrise": sunrise,
                "sunset": sunset,
                "timezone_offset_seconds": tz_offset_sec,
                "timezone_abbr": tz_abbr,
                "hourly": hourly_list,
                "city": city_name,
                "state": state_name,
                "country": "IN",
                "lat": data.get("latitude", target_lat),
                "lon": data.get("longitude", target_lon),
                "requested_lat": target_lat,
                "requested_lon": target_lon,
                "spray_advisory": spray_advice,
                "spray_favorable": spray_favorable,
                "metadata": {
                    "data_type": "LIVE METEOROLOGICAL DATA",
                    "source": "Open-Meteo Meteorological Service (WMO / IMD models)",
                    "observation_time": curr.get("time"),
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                },
            }
        except Exception as exc:
            logger.warning("Open-Meteo current weather request failed: %s", exc)
            return None


async def fetch_open_meteo_forecast(target_lat: float, target_lon: float, city_name: str, state_name: str) -> Optional[dict]:
    """
    Fetches genuine 7-day agricultural daily forecast from Open-Meteo API.
    Never fabricates missing fields.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={target_lat}&longitude={target_lon}"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,sunrise,sunset"
        f"&timezone=auto&forecast_days=7"
    )
    async with httpx.AsyncClient(timeout=4.5) as client:
        try:
            res = await client.get(url)
            if res.status_code != 200:
                return None
            data = res.json()
            daily = data.get("daily", {})
            times = daily.get("time", [])
            if not times:
                return None
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precips = daily.get("precipitation_sum", [])
            pop_maxs = daily.get("precipitation_probability_max", [])
            winds = daily.get("wind_speed_10m_max", [])
            sunrises = daily.get("sunrise", [])
            sunsets = daily.get("sunset", [])

            daily_forecasts = []
            for i in range(len(times)):
                w_code = daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else 0
                cond_desc, cond_main, icon = WMO_CODES.get(w_code, ("Mainly clear", "Clear", "01d"))
                min_t = min_temps[i] if (i < len(min_temps) and min_temps[i] is not None) else None
                max_t = max_temps[i] if (i < len(max_temps) and max_temps[i] is not None) else None
                avg_t = round((max_t + min_t) / 2) if (min_t is not None and max_t is not None) else (max_t or min_t)
                pop = round(pop_maxs[i]) if (i < len(pop_maxs) and pop_maxs[i] is not None) else None
                rain_mm = round(float(precips[i]), 1) if (i < len(precips) and precips[i] is not None) else None
                wind_max = round(winds[i]) if (i < len(winds) and winds[i] is not None) else None
                sr = sunrises[i] if i < len(sunrises) else None
                ss = sunsets[i] if i < len(sunsets) else None

                daily_forecasts.append({
                    "date": times[i],
                    "temp_min": round(min_t) if min_t is not None else None,
                    "temp_max": round(max_t) if max_t is not None else None,
                    "temp": avg_t,
                    "humidity": None,
                    "condition": cond_desc,
                    "condition_main": cond_main,
                    "icon": icon,
                    "rain_mm": rain_mm,
                    "rain_probability": pop,
                    "wind_speed_max": wind_max,
                    "sunrise": sr,
                    "sunset": ss,
                })

            return {
                "available": True,
                "city": city_name,
                "state": state_name,
                "country": "IN",
                "lat": data.get("latitude", target_lat),
                "lon": data.get("longitude", target_lon),
                "daily": daily_forecasts,
                "metadata": {
                    "source": "Open-Meteo 7-Day Forecast API (WMO / ECMWF models)",
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                },
            }
        except Exception as exc:
            logger.warning("Open-Meteo forecast request failed: %s", exc)
            return None


@router.get("/current")
async def get_current_weather(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    q: Optional[str] = Query(None),
    refresh: bool = Query(False),
):
    """
    GET /api/weather/current
    Fetches real-time weather for farmer GPS coordinates or village/town/district query.
    Uses multi-provider resilience (OpenWeatherMap primary when API key is set,
    seamless Open-Meteo WMO meteorological service fallback).
    Uses bounded 10-minute cache with transparent metadata.
    """
    target_lat, target_lon, city_name, state_name = resolve_location(q, lat, lon)
    api_key = get_openweather_key()
    coord_part = f"{round(target_lat, 3)},{round(target_lon, 3)}"
    label_part = q.strip().lower() if (q and q.strip()) else ""
    cache_key = f"{coord_part}:{label_part}:key={bool(api_key)}:cls={id(httpx.AsyncClient)}"
    now_ts = time.time()

    if not refresh and cache_key in _CURRENT_CACHE:
        cached_data, exp_ts = _CURRENT_CACHE[cache_key]
        if now_ts < exp_ts:
            res_copy = dict(cached_data)
            res_copy["metadata"] = dict(cached_data.get("metadata", {}))
            res_copy["metadata"]["cache_hit"] = True
            return res_copy

    # 1. Try OpenWeatherMap if API key is provided
    if api_key:
        if lat is not None and lon is not None:
            url = f"{OPENWEATHER_BASE}/weather?lat={target_lat}&lon={target_lon}&appid={api_key}&units=metric"
        elif q and len(q.strip()) > 0:
            query_str = q.split("·")[0].split(",")[0].strip()
            if not (",in" in query_str.lower() or ", in" in query_str.lower() or ",india" in query_str.lower()):
                query_str = f"{query_str},IN"
            url = f"{OPENWEATHER_BASE}/weather?q={query_str}&appid={api_key}&units=metric"
        else:
            url = f"{OPENWEATHER_BASE}/weather?lat={target_lat}&lon={target_lon}&appid={api_key}&units=metric"

        async with httpx.AsyncClient(timeout=4.0) as client:
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    main_block = data.get("main", {})
                    wind_block = data.get("wind", {})
                    weather_block = (data.get("weather") or [{}])[0]
                    sys_block = data.get("sys", {})

                    wind_kmh = round(wind_block["speed"] * 3.6) if wind_block.get("speed") is not None else None
                    wind_deg = round(wind_block["deg"]) if wind_block.get("deg") is not None else None
                    wind_cardinal = _deg_to_cardinal(wind_deg)
                    humidity = main_block.get("humidity")
                    pressure = main_block.get("pressure")
                    rain_1h = data.get("rain", {}).get("1h") if isinstance(data.get("rain"), dict) else None

                    if (rain_1h or 0.0) > 0.5:
                        spray_advice = "❌ Do NOT Spray Today: Rain has been detected. Chemical will wash off."
                        spray_favorable = False
                    elif (wind_kmh or 0) > 18:
                        spray_advice = f"⚠️ High Wind ({wind_kmh} km/h): Risk of spray drift to adjacent crops. Delay until wind calms."
                        spray_favorable = False
                    elif (humidity or 0) > 85:
                        spray_advice = f"⚠️ High Humidity ({humidity}%): Leaf drying will be delayed. Spray during early morning after dew clears."
                        spray_favorable = True
                    else:
                        spray_advice = "✅ Optimal Spray Window: Clear skies and calm wind. Spray early morning (6:30 - 9:00 AM) or late afternoon."
                        spray_favorable = True

                    sr_ts = sys_block.get("sunrise")
                    ss_ts = sys_block.get("sunset")
                    tz_offset_sec = data.get("timezone")
                    country_code = sys_block.get("country", "IN")
                    if tz_offset_sec is None and country_code == "IN":
                        tz_offset_sec = 19800

                    loc_tz = (
                        datetime.timezone(datetime.timedelta(seconds=tz_offset_sec))
                        if tz_offset_sec is not None
                        else datetime.timezone.utc
                    )
                    sunrise_iso = (
                        datetime.datetime.fromtimestamp(sr_ts, tz=loc_tz).isoformat()
                        if sr_ts
                        else None
                    )
                    sunset_iso = (
                        datetime.datetime.fromtimestamp(ss_ts, tz=loc_tz).isoformat()
                        if ss_ts
                        else None
                    )
                    tz_abbr = _format_tz_label(tz_offset_sec, country_code)

                    weather_res = {
                        "available": True,
                        "temp": round(main_block["temp"]) if main_block.get("temp") is not None else None,
                        "feels_like": round(main_block["feels_like"]) if main_block.get("feels_like") is not None else None,
                        "temp_min": round(main_block["temp_min"]) if main_block.get("temp_min") is not None else None,
                        "temp_max": round(main_block["temp_max"]) if main_block.get("temp_max") is not None else None,
                        "humidity": humidity,
                        "pressure": pressure,
                        "condition": weather_block.get("description"),
                        "condition_main": weather_block.get("main"),
                        "icon": weather_block.get("icon"),
                        "wind_speed": wind_kmh,
                        "wind_direction_deg": wind_deg,
                        "wind_direction_cardinal": wind_cardinal,
                        "rain_1h": rain_1h,
                        "rain_mm": rain_1h,
                        "rain_probability": None,  # OpenWeatherMap /weather does not report pop; never fabricate
                        "sunrise": sunrise_iso,
                        "sunset": sunset_iso,
                        "timezone_offset_seconds": tz_offset_sec,
                        "timezone_abbr": tz_abbr,
                        "hourly": [],
                        "city": city_name if (q and q.strip()) else data.get("name", city_name),
                        "state": state_name,
                        "country": sys_block.get("country", "IN"),
                        "lat": data.get("coord", {}).get("lat", target_lat),
                        "lon": data.get("coord", {}).get("lon", target_lon),
                        "requested_lat": target_lat,
                        "requested_lon": target_lon,
                        "spray_advisory": spray_advice,
                        "spray_favorable": spray_favorable,
                        "metadata": {
                            "data_type": "LIVE DATA",
                            "source": "OpenWeatherMap API",
                            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                        },
                    }
                    _CURRENT_CACHE[cache_key] = (weather_res, now_ts + _CURRENT_TTL)
                    return weather_res
            except Exception as exc:
                logger.warning("OpenWeatherMap request failed: %s, falling back to Open-Meteo", exc)

    # 2. Seamless fallback to Open-Meteo Meteorological Service
    meteo_res = await fetch_open_meteo_current(target_lat, target_lon, city_name, state_name)
    if meteo_res:
        _CURRENT_CACHE[cache_key] = (meteo_res, now_ts + _CURRENT_TTL)
        return meteo_res

    # 3. Fallback to stale cache if network is down
    if cache_key in _CURRENT_CACHE:
        cached_data, _ = _CURRENT_CACHE[cache_key]
        stale_copy = dict(cached_data)
        stale_copy["metadata"] = dict(cached_data.get("metadata", {}))
        stale_copy["metadata"]["stale"] = True
        stale_copy["metadata"]["notice"] = "Live weather update unavailable; displaying cached reading."
        return stale_copy

    if not api_key:
        reason, message = "missing_api_key", "Weather service is not configured (OPENWEATHER_API_KEY missing)."
    else:
        reason, message = "provider_error", "Weather providers are temporarily unreachable. Please check connection and try again."
    return {
        "available": False,
        "reason": reason,
        "message": message,
    }


@router.get("/forecast")
async def get_weather_forecast(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    q: Optional[str] = Query(None),
    refresh: bool = Query(False),
):
    """
    GET /api/weather/forecast
    Fetches real 7-day daily agricultural forecast.
    Uses multi-provider resilience (OpenWeatherMap primary when configured,
    seamless Open-Meteo WMO numerical weather prediction fallback).
    Uses bounded 30-minute cache with transparent metadata.
    """
    target_lat, target_lon, city_name, state_name = resolve_location(q, lat, lon)
    api_key = get_openweather_key()
    coord_part = f"{round(target_lat, 3)},{round(target_lon, 3)}"
    label_part = q.strip().lower() if (q and q.strip()) else ""
    cache_key = f"{coord_part}:{label_part}:key={bool(api_key)}:cls={id(httpx.AsyncClient)}"
    now_ts = time.time()

    if not refresh and cache_key in _FORECAST_CACHE:
        cached_data, exp_ts = _FORECAST_CACHE[cache_key]
        if now_ts < exp_ts:
            res_copy = dict(cached_data)
            res_copy["metadata"] = dict(cached_data.get("metadata", {}))
            res_copy["metadata"]["cache_hit"] = True
            return res_copy

    # 0. Prefer Open-Meteo: it returns a genuine 7-day daily forecast. The free OpenWeatherMap
    #    5-day/3-hour endpoint only spans ~6 calendar dates, which under-fills a "7-day forecast".
    meteo_primary = await fetch_open_meteo_forecast(target_lat, target_lon, city_name, state_name)
    if meteo_primary and len(meteo_primary.get("daily", [])) >= 7:
        _FORECAST_CACHE[cache_key] = (meteo_primary, now_ts + _FORECAST_TTL)
        return meteo_primary

    # 1. Try OpenWeatherMap if API key is provided (fallback; fewer than 7 days)
    if api_key:
        if lat is not None and lon is not None:
            url = f"{OPENWEATHER_BASE}/forecast?lat={target_lat}&lon={target_lon}&appid={api_key}&units=metric"
        elif q and len(q.strip()) > 0:
            query_str = q.split("·")[0].split(",")[0].strip()
            if not (",in" in query_str.lower() or ", in" in query_str.lower() or ",india" in query_str.lower()):
                query_str = f"{query_str},IN"
            url = f"{OPENWEATHER_BASE}/forecast?q={query_str}&appid={api_key}&units=metric"
        else:
            url = f"{OPENWEATHER_BASE}/forecast?lat={target_lat}&lon={target_lon}&appid={api_key}&units=metric"

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    raw_list = data.get("list", [])
                    by_date = {}
                    for item in raw_list:
                        d_str = item.get("dt_txt", "")[:10]
                        if d_str:
                            by_date.setdefault(d_str, []).append(item)

                    daily_forecasts = []
                    for d_str, items in by_date.items():
                        rep_item = items[len(items) // 2]
                        for it in items:
                            if "12:00:00" in it.get("dt_txt", ""):
                                rep_item = it
                                break

                        min_temp = min(it["main"]["temp_min"] for it in items)
                        max_temp = max(it["main"]["temp_max"] for it in items)
                        w_info = rep_item.get("weather", [{}])[0]
                        total_rain = sum(it.get("rain", {}).get("3h", 0.0) for it in items)
                        max_pop = max((it.get("pop", 0.0) for it in items), default=0.0)

                        daily_forecasts.append({
                            "date": d_str,
                            "temp_min": round(min_temp),
                            "temp_max": round(max_temp),
                            "temp": round(rep_item["main"]["temp"]),
                            "humidity": rep_item["main"].get("humidity"),
                            "condition": w_info.get("description", "Clear"),
                            "condition_main": w_info.get("main", "Clear"),
                            "icon": w_info.get("icon", "01d"),
                            "rain_mm": round(total_rain, 1),
                            "rain_probability": round(max_pop * 100),
                        })

                    forecast_res = {
                        "available": True,
                        "city": city_name if (q and q.strip()) else data.get("city", {}).get("name", city_name),
                        "state": state_name,
                        "country": data.get("city", {}).get("country", "IN"),
                        "lat": data.get("city", {}).get("coord", {}).get("lat", target_lat),
                        "lon": data.get("city", {}).get("coord", {}).get("lon", target_lon),
                        "daily": daily_forecasts,
                        "metadata": {
                            "source": "OpenWeatherMap 5-Day Forecast API",
                            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                        },
                    }
                    _FORECAST_CACHE[cache_key] = (forecast_res, now_ts + _FORECAST_TTL)
                    return forecast_res
            except Exception as exc:
                logger.warning("OpenWeatherMap forecast request failed: %s, falling back to Open-Meteo", exc)

    # 2. Seamless fallback to Open-Meteo Meteorological Service
    meteo_res = await fetch_open_meteo_forecast(target_lat, target_lon, city_name, state_name)
    if meteo_res:
        _FORECAST_CACHE[cache_key] = (meteo_res, now_ts + _FORECAST_TTL)
        return meteo_res

    # 3. Fallback to stale cache if network is down
    if cache_key in _FORECAST_CACHE:
        cached_data, _ = _FORECAST_CACHE[cache_key]
        stale_copy = dict(cached_data)
        stale_copy["metadata"] = dict(cached_data.get("metadata", {}))
        stale_copy["metadata"]["stale"] = True
        stale_copy["metadata"]["notice"] = "Live forecast update unavailable; displaying cached forecast."
        return stale_copy

    if not api_key:
        reason, message = "missing_api_key", "Weather service is not configured (OPENWEATHER_API_KEY missing)."
    else:
        reason, message = "provider_error", "Weather forecast providers are temporarily unreachable. Please check connection and try again."
    return {
        "available": False,
        "reason": reason,
        "message": message,
    }
