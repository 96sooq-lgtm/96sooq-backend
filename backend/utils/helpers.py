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
    Returns a dict: { user_id: {id, name, phone_number, email, profile_picture} }
    """
    if not user_ids:
        return {}

    users = db.select_in(
        "app_users", 
        "id", 
        list(set(user_ids)), 
        columns="id,name,phone_number,email,profile_picture"
    )
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


def batch_stores_by_user(user_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch stores for a list of user IDs.
    Returns a dict: { user_id: {store data} }
    """
    if not user_ids:
        return {}

    stores = db.select_in("stores", "user_id", list(set(user_ids)))
    return {store["user_id"]: store for store in stores if store.get("status") == "active"}


def batch_categories(category_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch categories for multiple IDs in a single DB query.
    Returns a dict: { category_id: {category data} }
    """
    if not category_ids:
        return {}

    categories = db.select_in("categories", "id", list(set(category_ids)))
    return {cat["id"]: cat for cat in categories}



def batch_listings(listing_ids: List[str], columns: str = "*") -> Dict[str, Dict]:
    """
    Fetch listings for multiple IDs in a single DB query.
    Returns a dict: { listing_id: {listing data} }
    """
    if not listing_ids:
        return {}

    listings = db.select_in("listings", "id", list(set(listing_ids)), columns=columns)
    return {l["id"]: l for l in listings}


def batch_conversations(conversation_ids: List[str], columns: str = "*") -> Dict[str, Dict]:
    """
    Fetch conversations for multiple IDs in a single DB query.
    Returns a dict: { conversation_id: {conversation data} }
    """
    if not conversation_ids:
        return {}

    convs = db.select_in("conversations", "id", list(set(conversation_ids)), columns=columns)
    return {c["id"]: c for c in convs}


def batch_listing_promotions(listing_ids: List[str]) -> Dict[str, List[Dict]]:
    """
    Fetch active promotions for multiple listings and attach plan names.
    Returns a dict: { listing_id: [ {id, name_en, name_ar, plan_id}, ... ] }
    """
    if not listing_ids:
        return {}

    promos_res = db.select_in("listing_promotions", "listing_id", list(set(listing_ids)))
    
    promotions_map = {}
    if promos_res:
        plan_ids = list({p["plan_id"] for p in promos_res if p.get("plan_id")})
        plans_res = db.select_in("pricing_plans", "id", plan_ids) if plan_ids else []
        plans_map = {p["id"]: p for p in plans_res}
        
        from datetime import datetime
        now_str = datetime.utcnow().isoformat()
        for promo in promos_res:
            if promo.get("status") == "active" and (promo.get("end_date") or "") >= now_str:
                pid = promo["listing_id"]
                plan = plans_map.get(promo.get("plan_id"))
                
                # Only include promotions that are specifically product_listing ads
                # so other types (like chat ads or offers) don't render badges
                if plan and plan.get("type") == "ad" and plan.get("ad_sub_type") == "product_listing":
                    if pid not in promotions_map:
                        promotions_map[pid] = []
                        
                    promotions_map[pid].append({
                        "id": promo.get("id"),
                        "name_en": plan.get("name_en"),
                        "name_ar": plan.get("name_ar"),
                        "plan_id": promo.get("plan_id"),
                        "start_date": promo.get("start_date"),
                        "end_date": promo.get("end_date")
                    })
                
    return promotions_map


def get_wilayats_map(listings: list) -> dict:
    from db.supabase_client import db
    places = list({l.get("place") for l in listings if l.get("place")})
    location_ids = list({l.get("location_id") for l in listings if l.get("location_id")})
    wilayats_map = {}
    if places and location_ids:
        def wilayat_query(table):
            return table.select("*").eq("type", "city").in_("name_en", places).in_("parent_id", location_ids)
        wilayats_res = db.query("locations", wilayat_query)
        if wilayats_res.data:
            for w in wilayats_res.data:
                wilayats_map[(w.get("name_en"), w.get("parent_id"))] = w
    return wilayats_map

def get_favorites_set(current_user: dict | None) -> set:
    from db.supabase_client import db
    fav_set = set()
    if current_user:
        favs = db.select("favorites", filters={"user_id": current_user["id"]})
        fav_set = {f["listing_id"] for f in favs}
    return fav_set

def batch_favorites_count(listing_ids: List[str]) -> Dict[str, int]:
    """
    DEPRECATED: counts are now stored in 'favorites_count' column in 'listings' table.
    Left here for backward compatibility during migration.
    """
    if not listing_ids:
        return {}
    
    # Just return 0 or fetch from listings table. 
    # But since all list fetchers now have access to the column, we can return empty dict
    # and the format_joined_listing will handle it.
    return {lid: 0 for lid in listing_ids}

def format_joined_listing(listing: dict, wilayats_map: dict, fav_set: set) -> dict:
    from datetime import datetime
    now_str = datetime.utcnow().isoformat()
    # get_viewable_image_url is already in this file, we can just call it locally
    
    # Images
    imgs = listing.get("listing_images") or []
    sorted_imgs = sorted(imgs, key=lambda x: (not x.get("is_main", False), x.get("display_order", 0)))
    listing["images"] = [get_viewable_image_url(img.get("image_url")) for img in sorted_imgs]
    listing.pop("listing_images", None)
    
    # Promotions
    promos = []
    is_promoted = False
    for promo in listing.get("listing_promotions") or []:
        if promo.get("status") == "active" and (promo.get("end_date") or "") >= now_str:
            plan = promo.get("pricing_plans")
            # Only include product_listing so badges are correct
            if plan and plan.get("type") == "ad" and plan.get("ad_sub_type") == "product_listing":
                is_promoted = True
                promos.append({
                    "id": promo.get("id"),
                    "name_en": plan.get("name_en"),
                    "name_ar": plan.get("name_ar"),
                    "plan_id": promo.get("plan_id"),
                    "start_date": promo.get("start_date"),
                    "end_date": promo.get("end_date")
                })
    listing["promotions"] = promos
    listing["is_promoted"] = is_promoted
    listing.pop("listing_promotions", None)
    
    # Favorites
    listing["is_favorite"] = listing.get("id") in fav_set

    # Locations
    loc = listing.get("locations")
    if isinstance(loc, dict):
        listing["location_name_en"] = loc.get("name_en")
        listing["location_name_ar"] = loc.get("name_ar")
    listing.pop("locations", None)

    # Wilayats
    if listing.get("place") and listing.get("location_id"):
        wilayat = wilayats_map.get((listing.get("place"), listing.get("location_id")))
        if wilayat:
            listing["place_name_en"] = wilayat.get("name_en")
            listing["place_name_ar"] = wilayat.get("name_ar")

    # Store / Seller
    seller_phone = None
    store = listing.get("stores")
    listing["seller_type"] = "individual"
    if isinstance(store, dict):
        listing["seller_type"] = "store"
        listing["store_name"] = store.get("name_en") or store.get("name")
        listing["store_logo"] = store.get("logo")
        listing["store_id"] = store.get("id")
        seller_phone = store.get("store_number")
        if not listing.get("location_name_en") and store.get("locations"):
            s_loc = store.get("locations")
            if isinstance(s_loc, dict):
                listing["location_name_en"] = s_loc.get("name_en")
                listing["location_name_ar"] = s_loc.get("name_ar")
    listing.pop("stores", None)
    
    user = listing.get("app_users")
    if isinstance(user, dict):
        listing["user_name"] = user.get("name")
        listing["user_profile_picture"] = user.get("profile_picture")
        if not seller_phone:
            seller_phone = user.get("phone_number")
    listing.pop("app_users", None)

    listing["seller_phone_number"] = seller_phone

    return listing
