"""تحويل عناوين العملاء إلى إحداثيات GPS (Google ثم OpenStreetMap كبديل)."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

# نفس مفتاح الخرائط المستخدم في الواجهة
DEFAULT_KEY = "AIzaSyC1kS8u0kFILegZQ1KZRX9mfAKAOsjxdNA"
NOMINATIM_UA = "LiftCoreElevatorApp/1.0"


def _maps_url(lat: float, lng: float, place_id: str | None = None) -> str:
    if place_id:
        return f"https://www.google.com/maps/search/?api=1&query_place_id={place_id}"
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def _geocode_google(query: str, *, api_key: str) -> tuple[float, float, str] | None:
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json?"
        + urllib.parse.urlencode({"address": query, "region": "sa", "language": "ar", "key": api_key})
    )
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except OSError:
        return None

    if data.get("status") != "OK" or not data.get("results"):
        return None

    result = data["results"][0]
    loc = result["geometry"]["location"]
    lat, lng = float(loc["lat"]), float(loc["lng"])
    return lat, lng, _maps_url(lat, lng, result.get("place_id"))


def _geocode_nominatim(query: str) -> tuple[float, float, str] | None:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "sa"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except OSError:
        return None

    if not data:
        return None

    lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
    return lat, lng, _maps_url(lat, lng)


def geocode_address(
    address: str = "",
    city: str = "",
    district: str = "",
    *,
    api_key: str | None = None,
    prefer_nominatim: bool = False,
) -> tuple[float, float, str] | None:
    """يرجع (lat, lng, maps_url) أو None."""
    full_parts = [p.strip() for p in (address, district, city, "Saudi Arabia") if p and str(p).strip()]
    district_parts = [p.strip() for p in (district, city or "Makkah", "Saudi Arabia") if p and str(p).strip()]
    if not district_parts:
        return None

    key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", DEFAULT_KEY)
    queries = []
    if full_parts:
        queries.append(", ".join(full_parts))
    district_query = ", ".join(district_parts)
    if district_query not in queries:
        queries.append(district_query)

    if not prefer_nominatim:
        for query in queries:
            result = _geocode_google(query, api_key=key)
            if result:
                return result

    for query in queries:
        result = _geocode_nominatim(query)
        if result:
            return result
    return None


def geocode_customer(
    customer,
    *,
    delay: float = 0.12,
    query_address: str | None = None,
    force: bool = False,
) -> bool:
    """يحدّث lat/lng/maps_url — query_address للبحث (مثلاً عنوان OSM كامل)."""
    if not force and customer.lat and customer.lng:
        try:
            float(customer.lat)
            float(customer.lng)
            return True
        except (TypeError, ValueError):
            pass

    result = geocode_address(
        address=query_address if query_address is not None else (customer.address or ""),
        city=customer.city or "",
        district=customer.district or "",
        prefer_nominatim=True,
    )
    if delay:
        time.sleep(max(delay, 0.25))
    if not result:
        return False

    lat, lng, maps_url = result
    customer.lat = str(lat)
    customer.lng = str(lng)
    customer.maps_url = maps_url
    return True
