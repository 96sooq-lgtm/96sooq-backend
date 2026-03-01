import os
import sys
import random
from uuid import uuid4
from datetime import datetime, timedelta, timezone

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.supabase_client import db

def log(msg):
    print(f"[*] {msg}")

def safe_execute(action, desc):
    try:
        return action()
    except Exception as e:
        print(f"[!] Error {desc}: {e}")
        return None

def main():
    log("Starting Dummy Data Generation...")

    # 1. Fetch Existing Locations
    locations = safe_execute(lambda: db.get_client().table("locations").select("*").execute(), "Fetching locations")
    if not locations or not locations.data:
        log("No locations found in DB. Need at least one governorate and wilayat.")
        return
    locations = locations.data
    
    governorates = [l for l in locations if l['parent_id'] is None]
    wilayats = [l for l in locations if l['parent_id'] is not None]

    if not governorates:
        # Create a dummy governorate and wilayat if not exists
        gov_data = {"name_en": "Muscat", "name_ar": "مسقط", "type": "state", "is_active": True}
        gov = db.insert("locations", gov_data)
        if not gov: return
        governorates = [gov]
        
    if not wilayats:
        wil_data = {"name_en": "Seeb", "name_ar": "السيب", "parent_id": governorates[0]['id'], "type": "city", "is_active": True}
        wil = db.insert("locations", wil_data)
        if not wil: return
        wilayats = [wil]

    log(f"Found {len(governorates)} governorates and {len(wilayats)} wilayats.")

    # 2. Fetch Pricing Plans
    plans = safe_execute(lambda: db.get_client().table("pricing_plans").select("*").execute(), "Fetching plans")
    plans = plans.data if plans else []
    
    listing_plans = [p for p in plans if p['type'] == 'listing']
    store_plans = [p for p in plans if p['type'] == 'store']
    
    # 3. Create Users
    dummy_users_data = []
    for i in range(1, 21):  # Create 20 users
        phone = f"+9689{random.randint(1000000, 9999999)}"
        dummy_users_data.append({
            "name": f"Dummy User {i}",
            "phone_number": phone,
            "email": f"user{i}_{uuid4().hex[:6]}@example.com",
            "is_active": True,
            "provider": "phone",
            "otp": "123456"
        })
    
    log(f"Creating 20 dummy users...")
    db.insert_many("app_users", dummy_users_data)
    
    # Fetch all users to get their IDs
    all_users = db.get_client().table("app_users").select("*").execute().data
    dummy_users = [u for u in all_users if u.get("name", "").startswith("Dummy User")]

    # 4. Fetch or Create Categories
    categories = db.get_client().table("categories").select("*").execute().data
    parents = [c for c in categories if c.get('parent_id') is None]
    subs = [c for c in categories if c.get('parent_id') is not None]
    
    if not parents:
        log("Creating base categories...")
        new_cats = [
            {"name_en": "Electronics", "name_ar": "إلكترونيات", "is_active": True},
            {"name_en": "Vehicles", "name_ar": "مركبات", "is_active": True},
            {"name_en": "Real Estate", "name_ar": "عقارات", "is_active": True}
        ]
        db.insert_many("categories", new_cats)
        categories = db.get_client().table("categories").select("*").execute().data
        parents = [c for c in categories if c.get('parent_id') is None]

    if not subs and parents:
        log("Creating sub categories...")
        new_subs = []
        for p in parents:
            new_subs.append({"name_en": f"Sub of {p['name_en']}", "name_ar": f"فرع من {p['name_ar']}", "parent_id": p['id'], "is_active": True})
            new_subs.append({"name_en": f"Sub 2 of {p['name_en']}", "name_ar": f"فرع 2 من {p['name_ar']}", "parent_id": p['id'], "is_active": True})
        db.insert_many("categories", new_subs)
        categories = db.get_client().table("categories").select("*").execute().data
        subs = [c for c in categories if c.get('parent_id') is not None]

    category_ids = [c['id'] for c in subs if c] if subs else [c['id'] for c in parents if c]

    # 5. Create Stores
    log("Creating 10 dummy stores...")
    store_statuses = ['active', 'pending_approval', 'rejected', 'expired']
    stores_data = []
    
    store_users = dummy_users[:10]
    for i, user in enumerate(store_users):
        gov = random.choice(governorates)
        wils_in_gov = [w for w in wilayats if w.get('parent_id') == gov['id']]
        wil = random.choice(wils_in_gov) if wils_in_gov else random.choice(wilayats)
        plan = random.choice(store_plans) if store_plans else None
        
        stores_data.append({
            "user_id": user['id'],
            "name": f"Dummy Store {i}",
            "name_ar": f"متجر تجريبي {i}",
            "description": f"This is a description for Dummy Store {i}.",
            "status": random.choice(store_statuses),
            "governorate_id": gov['id'],
            "wilayat": wil.get("id", wil.get("name_en", "Unknown")), 
            "plan_id": plan['id'] if plan else None,
            "store_number": user['phone_number']
        })
    db.insert_many("stores", stores_data)
    
    all_stores = db.get_client().table("stores").select("*").execute().data
    dummy_stores = [s for s in all_stores if s.get("name", "").startswith("Dummy Store")]

    # 6. Create Listings
    log("Creating 125 dummy listings...")
    listings_data = []
    listing_statuses = ['draft', 'pending_approval', 'active', 'active', 'active', 'rejected', 'sold', 'expired']
    images = [
        "https://dxkx3pfr9h6qq.cloudfront.net/uploads/dc71edb8-a8be-4f54-9aa6-f73171ab5534-banner_2.jpg",
        "https://dxkx3pfr9h6qq.cloudfront.net/uploads/f7e590b7-d5b6-4203-b9bf-65e338255f3b-hbna50555194_118_350.jpg"
    ]
    
    for i in range(125):
        user = random.choice(dummy_users)
        # 30% chance of being a store listing if the user has a store
        user_store = next((s for s in dummy_stores if s['user_id'] == user['id']), None)
        store_id = user_store['id'] if user_store and random.random() < 0.3 else None
        
        gov = random.choice(governorates)
        wils_in_gov = [w for w in wilayats if w.get('parent_id') == gov['id']]
        wil = random.choice(wils_in_gov) if wils_in_gov else random.choice(wilayats)
        
        cat_id = random.choice(category_ids)
        plan = random.choice(listing_plans) if listing_plans else None
        
        status = random.choice(listing_statuses)
        
        listings_data.append({
            "user_id": user['id'],
            "store_id": store_id,
            "category_id": cat_id,
            "title": f"Test Listing {i} - {status}",
            "description": f"Comprehensive description for Test Listing {i} to fulfill character requirements and show exactly what this product is.",
            "price": float(random.randint(50, 50000)),
            "currency": "AED",
            "status": status,
            "rejection_reason": "Random reason" if status == 'rejected' else None,
            "plan_id": plan['id'] if plan else None,
            "condition": random.choice(["new", "used"]),
            "place": wil.get("id", wil.get("name_en", "Unknown")),
            "location_id": gov['id']
        })
    
    # Insert in chunks of 50
    for i in range(0, len(listings_data), 50):
        db.insert_many("listings", listings_data[i:i+50])
        
    all_listings = db.get_client().table("listings").select("*").execute().data
    dummy_listings = [l for l in all_listings if l.get("title", "").startswith("Test Listing")]
    
    # Insert Listing Images
    log("Adding images to dummy listings...")
    images_data = []
    for l in dummy_listings:
        images_data.append({
            "listing_id": l['id'],
            "image_url": random.choice(images),
            "is_main": True,
            "display_order": 0
        })
    for i in range(0, len(images_data), 50):
        db.insert_many("listing_images", images_data[i:i+50])

    # 7. Create Transactions for different states
    log("Creating transactions for different states...")
    transactions_data = []
    transaction_statuses = ['pending', 'completed', 'failed']
    
    for l in dummy_listings[:50]: # create transactions for 50 listings
        if l['plan_id'] and l['status'] != 'draft':
            plan = next((p for p in listing_plans if p['id'] == l['plan_id']), None)
            t_status = 'completed' if l['status'] in ['active', 'sold', 'expired'] else random.choice(transaction_statuses)
            transactions_data.append({
                "user_id": l['user_id'],
                "amount": float(plan['price']) if plan else 10.0,
                "currency": "AED",
                "status": t_status,
                "payment_method": random.choice(["card", "wallet"]),
                "target_type": "listing",
                "target_id": l['id']
            })
            
    for s in dummy_stores:
        if s['plan_id']:
            plan = next((p for p in store_plans if p['id'] == s['plan_id']), None)
            t_status = 'completed' if s['status'] == 'active' else random.choice(transaction_statuses)
            transactions_data.append({
                "user_id": s['user_id'],
                "amount": float(plan['price']) if plan else 50.0,
                "currency": "AED",
                "status": t_status,
                "payment_method": random.choice(["card", "wallet"]),
                "target_type": "store",
                "target_id": s['id']
            })

    for i in range(0, len(transactions_data), 50):
        db.insert_many("transactions", transactions_data[i:i+50])

    # 8. Create User Subscriptions (Some already active and some pending/expired)
    log("Creating user subscriptions...")
    subs_data = []
    for user in dummy_users[:15]:
        plan = random.choice(listing_plans + store_plans) if listing_plans or store_plans else None
        if not plan: continue
        
        status = random.choice(['active', 'expired', 'cancelled'])
        now = datetime.now(timezone.utc)
        
        if status == 'active':
            start = now - timedelta(days=10)
            end = now + timedelta(days=20)
        elif status == 'expired':
            start = now - timedelta(days=40)
            end = now - timedelta(days=10)
        else:
            start = now
            end = now + timedelta(days=30)
            
        subs_data.append({
            "user_id": user['id'],
            "plan_id": plan['id'],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "remaining_quota": random.randint(0, 10),
            "status": status
        })
    
    if subs_data:
        db.insert_many("user_subscriptions", subs_data)

    log("Dummy data generation completed successfully!")

if __name__ == "__main__":
    main()
