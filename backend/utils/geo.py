"""
Geo-resolution utilities for location-based features.
Resolves user coordinates (lat/lng) to the nearest wilayat and governorate.
"""
import math
from typing import Dict, List, Optional, Tuple
from db.supabase_client import db
from utils.logger import get_logger

logger = get_logger(__name__)

# In-memory cache for locations (refreshed per process lifetime)
_locations_cache: Optional[List[Dict]] = None


def _get_all_locations_with_coords() -> List[Dict]:
    """Fetch all locations that have coordinates. Cached in-memory."""
    global _locations_cache
    if _locations_cache is not None:
        return _locations_cache

    def query_func(table):
        return (
            table.select("id, name_en, name_ar, type, parent_id, latitude, longitude")
            .eq("is_active", True)
            .not_.is_("latitude", "null")
            .not_.is_("longitude", "null")
        )

    result = db.query("locations", query_func)
    _locations_cache = result.data if result.data else []
    logger.info(f"Loaded {len(_locations_cache)} locations with coordinates into cache")
    return _locations_cache


def clear_location_cache():
    """Clear the in-memory location cache (call after seeding new coordinates)."""
    global _locations_cache
    _locations_cache = None


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth in kilometers.
    Uses the Haversine formula.
    """
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def resolve_location(
    lat: float, lng: float
) -> Dict:
    """
    Resolve user's coordinates to the nearest wilayat and its parent governorate.

    Returns:
        {
            "wilayat": { id, name_en, name_ar, parent_id, distance_km },
            "governorate": { id, name_en, name_ar },
            "nearby_governorate_ids": [ordered list of governorate IDs by distance]
        }
    """
    locations = _get_all_locations_with_coords()
    if not locations:
        logger.warning("No locations with coordinates found in database")
        return {"wilayat": None, "governorate": None, "nearby_governorate_ids": []}

    # Separate wilayats and governorates
    wilayats = [loc for loc in locations if loc["type"] == "city"]
    governorates = [loc for loc in locations if loc["type"] == "state"]

    # Find nearest wilayat
    nearest_wilayat = None
    min_distance = float("inf")

    for w in wilayats:
        w_lat = float(w["latitude"])
        w_lng = float(w["longitude"])
        dist = haversine_distance(lat, lng, w_lat, w_lng)
        if dist < min_distance:
            min_distance = dist
            nearest_wilayat = {**w, "distance_km": round(dist, 2)}

    # Find parent governorate
    governorate = None
    if nearest_wilayat:
        parent_id = nearest_wilayat.get("parent_id")
        for g in governorates:
            if g["id"] == parent_id:
                governorate = g
                break

    # Sort all governorates by distance for expanding radius
    gov_distances = []
    for g in governorates:
        g_lat = float(g["latitude"])
        g_lng = float(g["longitude"])
        dist = haversine_distance(lat, lng, g_lat, g_lng)
        gov_distances.append((g["id"], dist))

    gov_distances.sort(key=lambda x: x[1])
    nearby_gov_ids = [gid for gid, _ in gov_distances]

    return {
        "wilayat": nearest_wilayat,
        "governorate": governorate,
        "nearby_governorate_ids": nearby_gov_ids,
    }


def get_wilayat_names_in_governorate(governorate_id: str) -> List[str]:
    """Get all wilayat names (name_en) belonging to a governorate."""
    locations = _get_all_locations_with_coords()
    return [
        loc["name_en"]
        for loc in locations
        if loc["type"] == "city" and loc.get("parent_id") == governorate_id
    ]


def get_wilayats_for_governorates(governorate_ids: List[str]) -> List[str]:
    """Get all wilayat names for multiple governorates."""
    locations = _get_all_locations_with_coords()
    gov_set = set(governorate_ids)
    return [
        loc["name_en"]
        for loc in locations
        if loc["type"] == "city" and loc.get("parent_id") in gov_set
    ]


def resolve_location_by_name(
    governorate_name: Optional[str] = None,
    wilayat_name: Optional[str] = None,
) -> Dict:
    """
    Resolve a governorate/wilayat by name (en or ar) — no GPS needed.

    Returns:
        {
            "wilayat_name": str | None,   # exact name_en matched
            "gov_id": str | None,
            "gov_name_en": str | None,
            "gov_name_ar": str | None,
        }
    """
    locations = _get_all_locations_with_coords()
    governorates = [loc for loc in locations if loc["type"] == "state"]
    wilayats = [loc for loc in locations if loc["type"] == "city"]

    matched_gov = None
    matched_wilayat_name_en = None

    # Try to match governorate first
    if governorate_name:
        gov_name_lower = governorate_name.strip().lower()
        for g in governorates:
            if (
                g.get("name_en", "").lower() == gov_name_lower
                or g.get("name_ar", "").strip() == governorate_name.strip()
            ):
                matched_gov = g
                break

    # Try to match wilayat and derive governorate from it
    if wilayat_name:
        wil_name_lower = wilayat_name.strip().lower()
        for w in wilayats:
            if (
                w.get("name_en", "").lower() == wil_name_lower
                or w.get("name_ar", "").strip() == wilayat_name.strip()
            ):
                matched_wilayat_name_en = w["name_en"]
                if not matched_gov:
                    # Derive parent governorate
                    parent_id = w.get("parent_id")
                    for g in governorates:
                        if g["id"] == parent_id:
                            matched_gov = g
                            break
                break

    return {
        "wilayat_name": matched_wilayat_name_en,
        "gov_id": matched_gov["id"] if matched_gov else None,
        "gov_name_en": matched_gov.get("name_en") if matched_gov else None,
        "gov_name_ar": matched_gov.get("name_ar") if matched_gov else None,
    }
