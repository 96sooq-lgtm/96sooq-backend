import json
import uuid

def generate_id():
    return str(uuid.uuid4())

collection = {
    "info": {
        "name": "96sooq Full API Collection",
        "description": "Comprehensive API collection for the 96sooq Backend. Includes User Flows, Admin Flows, Feed, and Chat APIs. Updated 2026-03-05.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [
        {"key": "base_url", "value": "http://localhost:8000/api", "type": "string"},
        {"key": "admin_token", "value": "YOUR_ADMIN_TOKEN_HERE", "type": "string"},
        {"key": "user_token", "value": "YOUR_USER_TOKEN_HERE", "type": "string"}
    ],
    "item": [
        {
            "name": "1. Authentication",
            "item": [
                {
                    "name": "Admin Login",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/x-www-form-urlencoded"}],
                        "url": {"raw": "{{base_url}}/admin/login", "host": ["{{base_url}}"], "path": ["admin", "login"]},
                        "body": {
                            "mode": "urlencoded",
                            "urlencoded": [
                                {"key": "username", "value": "admin@96sooq.com", "type": "text"},
                                {"key": "password", "value": "admin123", "type": "text"}
                            ]
                        }
                    }
                },
                {
                    "name": "User OAuth Check (Google)",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/auth/oauth/check-user", "host": ["{{base_url}}"], "path": ["auth", "oauth", "check-user"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"provider": "google", "provider_id": "123456789", "email": "user@example.com"})
                        }
                    }
                },
                {
                    "name": "User OAuth Complete Profile",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/auth/oauth/complete-profile", "host": ["{{base_url}}"], "path": ["auth", "oauth", "complete-profile"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"provider": "google", "provider_id": "123456789", "email": "user@example.com", "name": "Test User", "phone_number": "+96812345678", "profile_picture": ""})
                        }
                    }
                }
            ]
        },
        {
            "name": "2. Public / Feed Flows",
            "item": [
                {
                    "name": "Get Main Feed (Filter by Governorate/Wilayat)",
                    "request": {
                        "method": "GET",
                        "description": "Main feed with location-aware expansion. Supports 'skip' or 'page' for pagination.",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/feed/?governorate=Muscat&wilayat=Seeb&limit=20&skip=0",
                            "host": ["{{base_url}}"],
                            "path": ["feed", ""],
                            "query": [
                                {"key": "governorate", "value": "Muscat", "description": "Governorate name in EN or AR"},
                                {"key": "wilayat", "value": "Seeb", "description": "Wilayat name in EN or AR"},
                                {"key": "limit", "value": "20"},
                                {"key": "skip", "value": "0", "description": "Offset-based pagination"},
                                {"key": "page", "value": "0", "disabled": True, "description": "Page-based pagination (0-based)"},
                                {"key": "category_id", "value": "", "disabled": True},
                                {"key": "condition", "value": "new", "disabled": True},
                                {"key": "min_price", "value": "10", "disabled": True},
                                {"key": "max_price", "value": "500", "disabled": True},
                                {"key": "seller_type", "value": "individual", "disabled": True}
                            ]
                        }
                    }
                },
                {
                    "name": "Get Category Feed",
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/feed/category/CAT_ID_HERE?governorate=Al Batinah North&skip=0",
                            "host": ["{{base_url}}"],
                            "path": ["feed", "category", "CAT_ID_HERE"],
                            "query": [
                                {"key": "governorate", "value": "Al Batinah North"},
                                {"key": "skip", "value": "0"}
                            ]
                        }
                    }
                },
                {
                    "name": "Get Location Offers",
                    "request": {
                        "method": "GET",
                        "description": "Returns both admin-created 'offers' and user-boosted 'top_offers'. Includes 'is_admin_offer' boolean in results.",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/feed/offers?governorate=Muscat&skip=0",
                            "host": ["{{base_url}}"],
                            "path": ["feed", "offers"],
                            "query": [
                                {"key": "governorate", "value": "Muscat"},
                                {"key": "skip", "value": "0"}
                            ]
                        }
                    }
                },
                {
                    "name": "Get Nearby Stores",
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/feed/nearby-stores?governorate=Muscat&wilayat=Bawshar&skip=0",
                            "host": ["{{base_url}}"],
                            "path": ["feed", "nearby-stores"],
                            "query": [
                                {"key": "governorate", "value": "Muscat"},
                                {"key": "wilayat", "value": "Bawshar"},
                                {"key": "skip", "value": "0"}
                            ]
                        }
                    }
                }
            ]
        },
        {
            "name": "3. User Flows - Common",
            "item": [
                {
                    "name": "Get My Profile",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "{{base_url}}/auth/me", "host": ["{{base_url}}"], "path": ["auth", "me"]}
                    }
                },
                {
                    "name": "Update Profile",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/auth/me", "host": ["{{base_url}}"], "path": ["auth", "me"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"name": "Updated Name", "phone_number": "+96899999999"})
                        }
                    }
                },
                {
                    "name": "Create Listing",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/listings/", "host": ["{{base_url}}"], "path": ["listings", ""]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "title": "Used iPhone 14",
                                "description": "Good condition",
                                "price": 250.0,
                                "currency": "OMR",
                                "condition": "used",
                                "category_id": "CAT_ID",
                                "location_id": "LOC_ID",
                                "images": ["url1", "url2"],
                                "target_audience": "everyone"
                            })
                        }
                    }
                },
                {
                    "name": "Get My Listings",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "{{base_url}}/listings/my-listings", "host": ["{{base_url}}"], "path": ["listings", "my-listings"]}
                    }
                },
                {
                    "name": "Checkout (Pay for Bundle/Boost)",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/payments/checkout", "host": ["{{base_url}}"], "path": ["payments", "checkout"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "listing_id": "YOUR_LISTING_ID_HERE",
                                "use_existing_quota": False,
                                "listing_plan_id": "PLAN_ID_FOR_PUBLISHING",
                                "ad_plan_id": "PLAN_ID_FOR_BOOSTING",
                                "ad_duration_days": 7
                            })
                        }
                    }
                }
            ]
        },
        {
            "name": "4. Admin Flows",
            "item": [
                {
                    "name": "Approve Listing",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [],
                        "url": {"raw": "{{base_url}}/admin/listings/LISTING_ID_HERE/approve", "host": ["{{base_url}}"], "path": ["admin", "listings", "LISTING_ID_HERE", "approve"]}
                    }
                }
            ]
        }
    ]
}

with open("96sooq_postman_collection_v2.json", "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=4)

print("Created 96sooq_postman_collection_v2.json successfully.")
