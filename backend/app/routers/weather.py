from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import httpx
import os
import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"

def get_openweather_key() -> str:
    return os.getenv("OPENWEATHER_API_KEY", "")

@router.get("/current")
async def get_current_weather(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    q: Optional[str] = Query(None)
):
    """
    GET /api/weather/current
    Fetches real-time weather from OpenWeatherMap for actual farmer GPS coordinates or city/district query.
    """
    api_key = get_openweather_key()
    if q and len(q.strip()) > 0:
        query_str = q.strip()
        if not (",in" in query_str.lower() or ", in" in query_str.lower() or ",india" in query_str.lower()):
            query_str = f"{query_str},IN"
        url = f"{OPENWEATHER_BASE}/weather?q={query_str}&appid={api_key}&units=metric"
    else:
        target_lat = lat if lat is not None else 12.9716
        target_lon = lon if lon is not None else 77.5946
        url = f"{OPENWEATHER_BASE}/weather?lat={target_lat}&lon={target_lon}&appid={api_key}&units=metric"
    
    async with httpx.AsyncClient(timeout=4.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                wind_kmh = round(data["wind"]["speed"] * 3.6)
                humidity = data["main"]["humidity"]
                rain_1h = data.get("rain", {}).get("1h", 0.0)
                
                if rain_1h > 0.5:
                    spray_advice = "❌ Do NOT Spray Today: Rain has been detected. Chemical will wash off."
                    spray_favorable = False
                elif wind_kmh > 18:
                    spray_advice = f"⚠️ High Wind ({wind_kmh} km/h): Risk of spray drift to adjacent crops. Delay until wind calms."
                    spray_favorable = False
                elif humidity > 85:
                    spray_advice = f"⚠️ High Humidity ({humidity}%): Leaf drying will be delayed. Spray during early morning after dew clears."
                    spray_favorable = True
                else:
                    spray_advice = "✅ Optimal Spray Window: Clear skies and calm wind. Spray early morning (6:30 - 9:00 AM) or late afternoon."
                    spray_favorable = True
                
                return {
                    "available": True,
                    "temp": round(data["main"]["temp"]),
                    "feels_like": round(data["main"]["feels_like"]),
                    "temp_min": round(data["main"].get("temp_min", data["main"]["temp"])),
                    "temp_max": round(data["main"].get("temp_max", data["main"]["temp"])),
                    "humidity": humidity,
                    "pressure": data["main"]["pressure"],
                    "condition": data["weather"][0]["description"],
                    "condition_main": data["weather"][0]["main"],
                    "icon": data["weather"][0]["icon"],
                    "wind_speed": wind_kmh,
                    "rain_1h": rain_1h,
                    "city": data.get("name", q or "Farm Location"),
                    "country": data.get("sys", {}).get("country", "IN"),
                    "lat": data.get("coord", {}).get("lat", lat or 12.9716),
                    "lon": data.get("coord", {}).get("lon", lon or 77.5946),
                    "spray_advisory": spray_advice,
                    "spray_favorable": spray_favorable,
                    "metadata": {
                        "data_type": "LIVE DATA",
                        "source": "OpenWeatherMap API",
                        "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
                    }
                }
        except Exception as exc:
            logger.error("OpenWeatherMap request failed: %s", exc)
            return {"available": False, "reason": "provider_error",
                    "message": "Weather provider is unreachable. Please try again later."}

    # No fabricated data: report the true state of the provider.
    if not api_key:
        reason, message = "missing_api_key", "Weather service is not configured (OPENWEATHER_API_KEY missing)."
    elif res.status_code == 401:
        reason, message = "invalid_api_key", "Weather provider rejected the API key."
    elif res.status_code == 404:
        reason, message = "location_not_found", "Location not found."
    else:
        reason, message = "provider_error", f"Weather provider returned HTTP {res.status_code}."
    logger.error("Weather unavailable: %s", reason)
    return {"available": False, "reason": reason, "message": message}


@router.get("/forecast")
async def get_weather_forecast(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    q: Optional[str] = Query(None)
):
    """
    GET /api/weather/forecast
    Fetches real 5-day / 3-hour forecast from OpenWeatherMap and aggregates into daily farm forecasts.
    """
    api_key = get_openweather_key()
    if q and len(q.strip()) > 0:
        query_str = q.strip()
        if not (",in" in query_str.lower() or ", in" in query_str.lower() or ",india" in query_str.lower()):
            query_str = f"{query_str},IN"
        url = f"{OPENWEATHER_BASE}/forecast?q={query_str}&appid={api_key}&units=metric"
    else:
        target_lat = lat if lat is not None else 12.9716
        target_lon = lon if lon is not None else 77.5946
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
                    # Pick midday representation (around 12:00) or median item
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
                        "humidity": rep_item["main"]["humidity"],
                        "condition": w_info.get("description", "Clear"),
                        "condition_main": w_info.get("main", "Clear"),
                        "icon": w_info.get("icon", "01d"),
                        "rain_mm": round(total_rain, 1),
                        "rain_probability": round(max_pop * 100)
                    })

                return {
                    "available": True,
                    "city": data.get("city", {}).get("name", q or "Farm Location"),
                    "country": data.get("city", {}).get("country", "IN"),
                    "daily": daily_forecasts,
                    "metadata": {
                        "source": "OpenWeatherMap 5-Day Forecast API",
                        "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
                    }
                }
        except Exception as exc:
            logger.error("OpenWeatherMap forecast request failed: %s", exc)
            return {"available": False, "reason": "provider_error", "message": "Weather forecast provider is unreachable."}

    if not api_key:
        reason, message = "missing_api_key", "Weather service is not configured (OPENWEATHER_API_KEY missing)."
    elif res.status_code == 401:
        reason, message = "invalid_api_key", "Weather provider rejected the API key."
    elif res.status_code == 404:
        reason, message = "location_not_found", "Location not found."
    else:
        reason, message = "provider_error", f"Weather provider returned HTTP {res.status_code}."
    return {"available": False, "reason": reason, "message": message}

