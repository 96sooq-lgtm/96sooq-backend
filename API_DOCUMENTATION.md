# 96sooq API Documentation

## Overview
This is a comprehensive OLX/Dubizzle-like marketplace platform with admin panel, user stores, listings, and approval workflows.

## Recent Changes Summary

### Database Schema
- ✅ Categories refactored with infinite nesting (`parent_id`) and dynamic attributes (`attributes_schema`)
- ✅ Added `image_url` to categories
- ✅ Created 10+ new tables: `stores`, `listings`, `listing_images`, `pricing_plans`, `transactions`, `ad_banners`, `favorites`, `store_reviews`, `offers`, `conversations`, `messages`

### Backend Code
- ✅ Updated Pydantic models for all new entities
- ✅ Implemented Store Management API (user + admin)
- ✅ Implemented Listing Management API (user + admin) with leaf-category validation
- ✅ Enhanced Category API with hierarchy traversal

---

## API Endpoints

### 1. Admin Authentication
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/admin/signup` | Register admin | None |
| `POST` | `/api/admin/login` | Admin login | None |
| `POST` | `/api/admin/change-password` | Change password | Admin |

### 2. Customer Authentication (OTP)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/auth/send-otp` | Send OTP to phone | None |
| `POST` | `/api/auth/verify-otp` | Verify OTP & get token | None |
| `POST` | `/api/auth/create-user` | Complete profile | Customer |

### 3. Categories (Public)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/categories/` | List root categories | None |
| `GET` | `/api/categories/?parent_id={id}` | List subcategories | None |
| `GET` | `/api/categories/{id}/is-leaf` | Check if leaf node | None |

### 4. Categories (Admin)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/admin/categories/` | Create category | Admin |
| `GET` | `/api/admin/categories/` | List all categories | Admin |
| `GET` | `/api/admin/categories/{id}` | Get category | Admin |
| `PUT` | `/api/admin/categories/{id}` | Update category | Admin |
| `DELETE` | `/api/admin/categories/{id}` | Delete category | Admin |

### 5. Stores (User)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/stores/` | Create store | Customer |
| `GET` | `/api/stores/` | List active stores | None |
| `GET` | `/api/stores/?user_id={id}` | List user's stores | None |
| `GET` | `/api/stores/{id}` | Get store details | None |
| `PUT` | `/api/stores/{id}` | Update store | Customer (Owner) |

### 6. Stores (Admin)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `PUT` | `/api/admin/stores/{id}/approve` | Approve store | Admin |
| `PUT` | `/api/admin/stores/{id}/reject` | Reject store | Admin |

### 7. Listings (User)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/listings/` | Create listing | Customer |
| `GET` | `/api/listings/` | List active listings | None |
| `GET` | `/api/listings/?category_id={id}` | Filter by category | None |
| `GET` | `/api/listings/?store_id={id}` | Filter by store | None |
| `GET` | `/api/listings/?search={term}` | Search by title | None |
| `GET` | `/api/listings/{id}` | Get listing details | None |
| `PUT` | `/api/listings/{id}` | Update listing | Customer (Owner) |

### 8. Listings (Admin)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `PUT` | `/api/admin/listings/{id}/approve` | Approve listing | Admin |
| `PUT` | `/api/admin/listings/{id}/reject?reason={text}` | Reject listing | Admin |

---

## User Flows

### Flow 1: User Registration & Profile
```
1. User enters phone number → POST /api/auth/send-otp
2. System sends OTP (MVP: 123456)
3. User verifies OTP → POST /api/auth/verify-otp
4. System returns JWT token + user data
5. User sets name → POST /api/auth/create-user (with token)
```

### Flow 2: Admin Login
```
1. Admin enters email/password → POST /api/admin/login
2. System returns JWT token
3. Admin uses token for all protected routes
```

### Flow 3: Create Category Hierarchy
```
Admin creates:
1. Root: Vehicles → POST /api/admin/categories/ {"name": "Vehicles"}
2. Child: Cars → POST /api/admin/categories/ {"name": "Cars", "parent_id": "<vehicles_id>"}
3. Leaf with Attributes: Toyota → POST /api/admin/categories/ 
   {
     "name": "Toyota", 
     "parent_id": "<cars_id>",
     "attributes_schema": [
       {"name": "fuel_type", "type": "select", "options": ["Petrol", "Diesel"]},
       {"name": "year", "type": "number"}
     ]
   }
```

### Flow 4: User Creates Store
```
1. User authenticates → JWT token
2. User creates store → POST /api/stores/ (with token)
   {
     "name": "Ahmed's Auto Shop",
     "description": "Best deals on cars"
   }
3. Store status: "pending_approval"
4. Admin approves → PUT /api/admin/stores/{id}/approve
5. Store status: "active"
```

### Flow 5: User Creates Listing
```
1. User authenticates → JWT token
2. User creates listing → POST /api/listings/ (with token)
   {
     "category_id": "<leaf_category_id>",
     "store_id": "<optional_store_id>",
     "title": "Toyota Camry 2020",
     "description": "Mint condition",
     "price": 75000,
     "attributes_values": {"fuel_type": "Petrol", "year": 2020},
     "images": ["https://example.com/img1.jpg"]
   }
3. System validates:
   - Category is leaf node ✓
   - User owns store (if provided) ✓
4. Listing status: "pending_approval"
5. Admin reviews and approves → PUT /api/admin/listings/{id}/approve
6. Listing status: "active"
7. Listing appears in public searches
```

### Flow 6: Guest User Browses
```
1. Get root categories → GET /api/categories/
2. Select "Vehicles" → GET /api/categories/?parent_id={vehicles_id}
3. Select "Cars" → GET /api/categories/?parent_id={cars_id}
4. View "Toyota" listings → GET /api/listings/?category_id={toyota_id}
5. View listing details → GET /api/listings/{listing_id}
```

---

## Key Payloads

### Create Category (with Hierarchy & Attributes)
```json
POST /api/admin/categories/
{
  "name": "Toyota",
  "parent_id": "uuid-of-cars-category",
  "image_url": "https://example.com/toyota.png",
  "attributes_schema": [
    {
      "name": "fuel_type",
      "type": "select",
      "options": ["Petrol", "Diesel", "Hybrid"]
    },
    {
      "name": "year",
      "type": "number"
    },
    {
      "name": "transmission",
      "type": "select",
      "options": ["Automatic", "Manual"]
    }
  ]
}
```

### Create Store
```json
POST /api/stores/
Authorization: Bearer <customer_token>

{
  "name": "Ahmed's Auto Shop",
  "description": "Premium cars at best prices",
  "logo_url": "https://example.com/logo.png",
  "cover_image_url": "https://example.com/cover.jpg"
}
```

### Create Listing
```json
POST /api/listings/
Authorization: Bearer <customer_token>

{
  "category_id": "uuid-of-leaf-category",
  "store_id": "uuid-of-store (optional)",
  "title": "Toyota Camry 2020 - Low Mileage",
  "description": "Excellent condition, single owner",
  "price": 75000,
  "currency": "AED",
  "attributes_values": {
    "fuel_type": "Petrol",
    "year": 2020,
    "transmission": "Automatic"
  },
  "location": {
    "lat": 25.2048,
    "lng": 55.2708,
    "address": "Dubai, UAE"
  },
  "images": [
    "https://example.com/img1.jpg",
    "https://example.com/img2.jpg"
  ]
}
```

---

## Business Rules

1. **Category Hierarchy**: Infinite nesting allowed. Only leaf categories can have listings.
2. **First Store Free**: Implementation pending (requires pricing plan logic).
3. **All Uploads Require Approval**: Stores, Listings, Banners → Admin must approve.
4. **Status Flow**: `pending_approval` → `active` (approved) or `rejected` (with reason).
5. **Dynamic Attributes**: Leaf categories define schema; listings provide values.

---

## Next Steps (Pending Implementation)

- [ ] Pricing Plans API (Admin CRUD)
- [ ] Transaction/Payment Integration
- [ ] Ad Banners API
- [ ] Favorites API
- [ ] Store Reviews API
- [ ] Offers API
- [ ] Chat/Messaging API
