"""
Shared helper functions used across multiple route modules.
"""
from typing import Optional, List, Dict
from utils.storage import s3_client
from db.supabase_client import db


def get_viewable_image_url(image_url_or_path: Optional[str]) -> Optional[str]:
    """
    Convert image URL or file path to a viewable URL.
    - If it's already a full URL (http/https), return as-is
    - If it's a file_path (starts with folder name), generate presigned URL
    """
    if not image_url_or_path:
        return None

    if image_url_or_path.startswith(('http://', 'https://')):
        return image_url_or_path

    if s3_client:
        presigned_url = s3_client.generate_presigned_url(image_url_or_path, expiration=3600)
        return presigned_url if presigned_url else image_url_or_path

    return image_url_or_path


def batch_listing_images(listing_ids: List[str]) -> Dict[str, List[str]]:
    """
    Fetch images for multiple listings in a single DB query.
    Returns a dict: { listing_id: [url1, url2, ...] }
    """
    if not listing_ids:
        return {}

    all_images = db.select_in("listing_images", "listing_id", listing_ids)

    images_map: Dict[str, List[dict]] = {}
    for img in all_images:
        lid = img["listing_id"]
        images_map.setdefault(lid, []).append(img)

    result: Dict[str, List[str]] = {}
    for lid, imgs in images_map.items():
        sorted_imgs = sorted(imgs, key=lambda x: (not x.get("is_main", False), x.get("display_order", 0)))
        result[lid] = [get_viewable_image_url(img["image_url"]) for img in sorted_imgs]

    return result


def batch_user_info(user_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch user info for multiple user IDs in a single DB query.
    Returns a dict: { user_id: {id, name, phone_number, email} }
    """
    if not user_ids:
        return {}

    users = db.select_in("app_users", "id", list(set(user_ids)), columns="id,name,phone_number,email")
    return {u["id"]: u for u in users}


def batch_locations(location_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch locations for multiple IDs in a single DB query.
    Returns a dict: { location_id: {location data} }
    """
    if not location_ids:
        return {}

    locations = db.select_in("locations", "id", list(set(location_ids)))
    return {loc["id"]: loc for loc in locations}


def batch_stores(store_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch stores for multiple IDs in a single DB query.
    Returns a dict: { store_id: {store data} }
    """
    if not store_ids:
        return {}

    stores = db.select_in("stores", "id", list(set(store_ids)))
    return {store["id"]: store for store in stores}

