import json
import uuid

def generate_id():
    return str(uuid.uuid4())

collection = {
    "info": {
        "name": "96sooq Full API Collection",
        "description": "Comprehensive API collection for the 96sooq Backend. Includes User Flows (Individual & Store), Admin Flows, Feed, and Chat APIs.",
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
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/feed/?governorate=Muscat&wilayat=Seeb&limit=20&skip=0",
                            "host": ["{{base_url}}"],
                            "path": ["feed", ""],
                            "query": [
                                {"key": "governorate", "value": "Muscat", "description": "Governorate name in EN or AR"},
                                {"key": "wilayat", "value": "Seeb", "description": "Wilayat name in EN or AR"},
                                {"key": "limit", "value": "20"},
                                {"key": "skip", "value": "0"},
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
                            "raw": "{{base_url}}/feed/category/CAT_ID_HERE?governorate=Al Batinah North",
                            "host": ["{{base_url}}"],
                            "path": ["feed", "category", "CAT_ID_HERE"],
                            "query": [
                                {"key": "governorate", "value": "Al Batinah North"}
                            ]
                        }
                    }
                },
                {
                    "name": "Get Location Offers",
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/feed/offers?governorate=Muscat",
                            "host": ["{{base_url}}"],
                            "path": ["feed", "offers"],
                            "query": [
                                {"key": "governorate", "value": "Muscat"}
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
                            "raw": "{{base_url}}/feed/nearby-stores?governorate=Muscat&wilayat=Bawshar",
                            "host": ["{{base_url}}"],
                            "path": ["feed", "nearby-stores"],
                            "query": [
                                {"key": "governorate", "value": "Muscat"},
                                {"key": "wilayat", "value": "Bawshar"}
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
                    "name": "Report Listing",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/listings/LISTING_ID_HERE/report?reason=Inappropriate content",
                            "host": ["{{base_url}}"],
                            "path": ["listings", "LISTING_ID_HERE", "report"],
                            "query": [{"key": "reason", "value": "Inappropriate content"}]
                        }
                    }
                },
                {
                    "name": "Report User",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/users/TARGET_USER_ID/report?reason=Scam account",
                            "host": ["{{base_url}}"],
                            "path": ["users", "TARGET_USER_ID", "report"],
                            "query": [{"key": "reason", "value": "Scam account"}]
                        }
                    }
                },
                {
                    "name": "Checkout (Pay for Listing & Boost)",
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
                                "listing_plan_id": "PLAN_ID_HERE",
                                "ad_plan_id": None,
                                "ad_duration_days": 1
                            })
                        }
                    }
                }
            ]
        },
        {
            "name": "4. User Flows - Store Specific",
            "item": [
                {
                    "name": "Check Existing Store",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "{{base_url}}/stores/check", "host": ["{{base_url}}"], "path": ["stores", "check"]}
                    }
                },
                {
                    "name": "Create Store",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/stores/", "host": ["{{base_url}}"], "path": ["stores", ""]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "name_en": "My Super Store",
                                "name_ar": "متجري",
                                "description_en": "Best deals",
                                "description_ar": "أفضل العروض",
                                "logo": "https://example.com/logo.png",
                                "banner": "https://example.com/banner.png",
                                "phone_number": "+96877777777",
                                "whatsapp_number": "+96877777777",
                                "email": "store@example.com",
                                "governorate_id": "GOV_ID",
                                "wilayat_id": "WILAYAT_ID",
                                "address": "Market Street No 5",
                                "commercial_register_number": "CR12345"
                            })
                        }
                    }
                },
                {
                    "name": "Update Store",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/stores/STORE_ID_HERE", "host": ["{{base_url}}"], "path": ["stores", "STORE_ID_HERE"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "description_en": "Updated text"
                            })
                        }
                    }
                }
            ]
        },
        {
            "name": "5. Chat APIs",
            "item": [
                {
                    "name": "Initiate Chat (Make Deal)",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "url": {"raw": "{{base_url}}/chats/initiate", "host": ["{{base_url}}"], "path": ["chats", "initiate"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"listing_id": "LISTING_ID_HERE"})
                        }
                    }
                },
                {
                    "name": "Get Inbox",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "{{base_url}}/chats/inbox", "host": ["{{base_url}}"], "path": ["chats", "inbox"]}
                    }
                },
                {
                    "name": "Get Conversation Messages",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "{{base_url}}/chats/CONV_ID_HERE/messages", "host": ["{{base_url}}"], "path": ["chats", "CONV_ID_HERE", "messages"]}
                    }
                },
                {
                    "name": "Mark Chat as Read",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{user_token}}", "type": "string"}]},
                        "method": "POST",
                        "header": [],
                        "url": {"raw": "{{base_url}}/chats/CONV_ID_HERE/read", "host": ["{{base_url}}"], "path": ["chats", "CONV_ID_HERE", "read"]}
                    }
                }
            ]
        },
        {
            "name": "6. Admin Flows",
            "item": [
                {
                    "name": "Get All Listings (Admin)",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/admin/listings/?status=pending_approval",
                            "host": ["{{base_url}}"],
                            "path": ["admin", "listings", ""],
                            "query": [
                                {"key": "status", "value": "pending_approval"}
                            ]
                        }
                    }
                },
                {
                    "name": "Approve Listing",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [],
                        "url": {"raw": "{{base_url}}/admin/listings/LISTING_ID_HERE/approve", "host": ["{{base_url}}"], "path": ["admin", "listings", "LISTING_ID_HERE", "approve"]}
                    }
                },
                {
                    "name": "Reject Listing",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/admin/listings/LISTING_ID_HERE/reject?reason=Violates Terms",
                            "host": ["{{base_url}}"],
                            "path": ["admin", "listings", "LISTING_ID_HERE", "reject"],
                            "query": [{"key": "reason", "value": "Violates Terms"}]
                        }
                    }
                },
                {
                    "name": "Get Admin General Reports",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/admin/users/reports?status=pending",
                            "host": ["{{base_url}}"],
                            "path": ["admin", "users", "reports"],
                            "query": [{"key": "status", "value": "pending"}]
                        }
                    }
                },
                {
                    "name": "Update Report Status",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/admin/users/reports/REPORT_ID_HERE?new_status=reviewed",
                            "host": ["{{base_url}}"],
                            "path": ["admin", "users", "reports", "REPORT_ID_HERE"],
                            "query": [{"key": "new_status", "value": "reviewed"}]
                        }
                    }
                },
                {
                    "name": "Suspend/Unsuspend User",
                    "request": {
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]},
                        "method": "PUT",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/admin/users/USER_ID_HERE/status?is_active=false",
                            "host": ["{{base_url}}"],
                            "path": ["admin", "users", "USER_ID_HERE", "status"],
                            "query": [{"key": "is_active", "value": "false"}]
                        }
                    }
                }
            ]
        }
    ]
}

with open("96sooq_postman_collection.json", "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=4)

print("Created 96sooq_postman_collection.json successfully.")
