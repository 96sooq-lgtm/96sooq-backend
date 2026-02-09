# Postman Collection - 96sooq Platform

## Overview

This Postman collection provides complete end-to-end API testing for the 96sooq marketplace platform.

**File:** `96sooq_complete.postman_collection.json`

---

## What's Included

### 1. Authentication (3 methods)
- ✅ **Admin Auth** - Signup & Login
- ✅ **OAuth** - Google/Apple/Facebook (2-step flow)
- ✅ **Phone OTP** - Legacy authentication

### 2. Categories
- ✅ **Admin** - Create, Read, Update, Delete categories
- ✅ **Public** - Browse categories, check leaf nodes
- ✅ **Dynamic Attributes** - Full schema examples

### 3. Stores
- ✅ **User** - Create, list, update stores
- ✅ **Admin** - Approve/reject stores

### 4. Listings
- ✅ **User** - Create (free/paid), list, search, update
- ✅ **Admin** - Approve/reject listings
- ✅ **Admin** - Approve/reject listings
- ✅ **Payment Flow** - First free, 2nd+ requires plan_id
- ✅ **Status Updates** - User can mark as sold/expired

### 5. New Features (Reviews, Chat, Ads)
- ✅ **Reviews** - Rate and review stores
- ✅ **Chat** - Real-time negotiation (Conversations & Messages)
- ✅ **Ads** - Create and list banner ads
- ✅ **Plans** - Admin management of pricing plans

---

## Quick Start

### Step 1: Import Collection

1. Open Postman
2. Click **Import**
3. Select `96sooq_complete.postman_collection.json`
4. Collection imported! ✅

### Step 2: Set Environment Variables

Create a new environment with these variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `base_url` | `http://localhost:8000` | Backend server URL |
| `admin_token` | _(auto-filled)_ | Admin JWT token |
| `customer_token` | _(auto-filled)_ | Customer JWT token |

**Note:** Tokens are automatically saved when you login!

### Step 3: Start Testing

Run requests in this order for best results:

```
1. Authentication → Admin Auth → Admin Signup
2. Authentication → Admin Auth → Admin Login (saves token)
3. Categories → Admin → Create Root Category
4. Categories → Admin → Create Sub-Category with Attributes
5. Authentication → OAuth → Step 1 - Check User (saves token)
6. Listings → User → Create First Listing (FREE)
```

---

## Folder Structure

```
96sooq Platform - Complete API
│
├── 1. Authentication
│   ├── Admin Auth
│   │   ├── Admin Signup
│   │   └── Admin Login (auto-saves token)
│   ├── OAuth (Google/Apple/Facebook)
│   │   ├── Step 1 - Check User Exists (auto-saves token)
│   │   └── Step 2 - Complete Profile (auto-saves token)
│   └── Phone OTP (Legacy)
│       ├── Send OTP
│       ├── Verify OTP (auto-saves token)
│       └── Create User Profile
│
├── 2. Categories
│   ├── Admin - Category Management
│   │   ├── Create Root Category
│   │   ├── Create Sub-Category with Attributes ⭐
│   │   ├── List All Categories
│   │   ├── Get Category Details
│   │   ├── Update Category
│   │   └── Delete Category
│   └── Public - Browse Categories
│       ├── Get Root Categories
│       ├── Get Sub-Categories
│       └── Check if Leaf Category
│
├── 3. Stores
│   ├── User - Store Operations
│   │   ├── Create Store
│   │   ├── List All Active Stores
│   │   ├── List My Stores
│   │   ├── Get Store Details
│   │   └── Update My Store
│   └── Admin - Store Approval
│       ├── Approve Store
│       └── Reject Store
│
└── 4. Listings
    ├── User - Listing Operations
    │   ├── Create First Listing (FREE) ⭐
    │   ├── Create Second Listing (PAID) ⭐
    │   ├── List All Active Listings
    │   ├── List Listings by Category
    │   ├── Search Listings
    │   ├── Get Listing Details
    │   └── Update My Listing
    └── Admin - Listing Approval
        ├── List All Pending Listings
        ├── List All Listings (Any Status)
        ├── Approve Listing ⭐
        └── Reject Listing

├── 5. Reviews
│   ├── Create Store Review
│   └── List Store Reviews
│
├── 6. Chat
│   ├── Start Conversation
│   ├── List My Conversations
│   ├── Send Message
│   └── Get Messages
│
├── 7. Ads (Banners)
│   ├── Create Ad
│   └── List Active Ads
│
└── 8. Pricing Plans
    ├── Create Plan (Admin)
    └── List Plans
```

⭐ = Key endpoints with special features

---

## Example Workflows

### Workflow 1: Complete Category Setup

```
1. Admin Login
   ↓
2. Create Root Category "Vehicles"
   → Response: { "id": "550e8400..." }
   → SAVE THIS ID!
   ↓
3. Create Sub-Category "Cars" (set parent_id from step 2)
   → Include attributes_schema
   → Response: { "id": "660e8400..." }
   ↓
4. Check if "Cars" is leaf
   → GET /api/categories/660e8400.../is-leaf
   → Response: { "is_leaf": true }
```

### Workflow 2: User Creates First Listing (Free)

```
1. OAuth Login (Step 1 + 2)
   → Token saved automatically
   ↓
2. Browse Categories
   → GET /api/categories/
   → Select category
   ↓
3. Create First Listing
   → plan_id: null
   → Response: { "status": "pending_approval" }
   ↓
4. Admin Approves
   → PUT /api/admin/listings/{id}/approve
   → Response: { "status": "active" }
```

### Workflow 3: User Creates Second Listing (Paid)

```
1. User already logged in
   ↓
2. Create Second Listing
   → plan_id: "plan-001" (REQUIRED!)
   → Response: { "status": "pending_approval" }
   ↓
OR if plan_id missing:
   → Response: 402 Payment Required
```

---

## Request Examples with Dummy Data

### 1. Create Category with Attributes

```json
POST /api/admin/categories/
Authorization: Bearer {{admin_token}}

{
  "name": "Cars",
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "attributes_schema": [
    {
      "key": "fuel_type",
      "label_en": "Fuel Type",
      "label_ar": "نوع الوقود",
      "type": "select",
      "required": true,
      "options": ["Petrol", "Diesel", "Hybrid", "Electric"]
    },
    {
      "key": "year",
      "label_en": "Year",
      "type": "number",
      "required": true
    }
  ]
}
```

### 2. OAuth Sign-In (New User)

```json
// Step 1: Check User
POST /api/auth/oauth/check-user

{
  "provider": "google",
  "provider_id": "google_123456789",
  "email": "ahmed@gmail.com"
}

Response: { "exists": false, "email": "ahmed@gmail.com" }

// Step 2: Complete Profile
POST /api/auth/oauth/complete-profile

{
  "provider": "google",
  "provider_id": "google_123456789",
  "email": "ahmed@gmail.com",
  "name": "Ahmed Ali",
  "phone_number": "+971501234567"
}

Response: { "access_token": "..." } ← Saved automatically!
```

### 3. Create Listing (First = Free)

```json
POST /api/listings/
Authorization: Bearer {{customer_token}}

{
  "category_id": "660e8400-e29b-41d4-a716-446655440001",
  "title": "Toyota Camry 2020",
  "price": 75000,
  "plan_id": null,  ← No payment needed!
  "attributes_values": {
    "fuel_type": "Petrol",
    "year": 2020,
    "transmission": "Automatic"
  },
  "images": ["https://cdn.example.com/car1.jpg"]
}
```

### 4. Create Listing (Second = Paid)

```json
POST /api/listings/
Authorization: Bearer {{customer_token}}

{
  "category_id": "660e8400-e29b-41d4-a716-446655440001",
  "title": "Honda Civic 2019",
  "price": 65000,
  "plan_id": "plan-001",  ← REQUIRED!
  "attributes_values": {
    "fuel_type": "Petrol",
    "year": 2019
  }
}
```

---

## Auto-Save Token Scripts

Some requests have **Test Scripts** that automatically save tokens to environment:

```javascript
// Admin Login → Saves admin_token
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set("admin_token", jsonData.access_token);
}
```

**Requests with auto-save:**
- ✅ Admin Login
- ✅ OAuth Check User (if exists)
- ✅ OAuth Complete Profile
- ✅ Verify OTP

---

## Response Examples

### Success Response (Category Created)
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "name_en": "Cars",
  "name_ar": "سيارات",
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "attributes_schema": [...],
  "is_active": true,
  "created_at": "2026-02-02T10:00:00Z"
}
```

### Error Response (Payment Required)
```json
{
  "detail": "Payment required. This is not your first listing. Please select a pricing plan.",
  "status_code": 402
}
```

### Error Response (Unauthorized)
```json
{
  "detail": "Not authenticated",
  "status_code": 401
}
```

---

## Common Issues & Solutions

### Issue 1: 401 Unauthorized

**Problem:** Token not set or expired

**Solution:**
1. Check environment has `admin_token` or `customer_token`
2. Re-run login request
3. Token is auto-saved if script exists

### Issue 2: 402 Payment Required

**Problem:** Creating 2nd+ listing without plan_id

**Solution:**
- Add `"plan_id": "plan-001"` to request body
- First listing is free, subsequent need payment

### Issue 3: 400 Bad Request (Category not leaf)

**Problem:** Trying to create listing in non-leaf category

**Solution:**
1. Use `/api/categories/{id}/is-leaf` to check
2. If `is_leaf: false`, select a sub-category
3. Only leaf categories allow listings

### Issue 4: Invalid parent_id

**Problem:** Using example IDs instead of real IDs

**Solution:**
1. Create root category first
2. Copy actual `id` from response
3. Use that as `parent_id` for sub-category

---

## Testing Checklist

Use this checklist to verify all features:

```
Authentication:
[ ] Admin can signup
[ ] Admin can login (token saved)
[ ] OAuth user can check existence
[ ] OAuth new user can complete profile (token saved)
[ ] Phone OTP sends successfully
[ ] Phone OTP verifies (token saved)

Categories:
[ ] Admin can create root category
[ ] Admin can create sub-category with attributes
[ ] Public can browse root categories
[ ] Public can browse sub-categories
[ ] Can check if category is leaf

Stores:
[ ] User can create store
[ ] Store defaults to pending_approval
[ ] Admin can approve store
[ ] Admin can reject store

Listings:
[ ] User can create first listing (free, no plan_id)
[ ] First listing has status: pending_approval
[ ] Creating 2nd listing without plan_id returns 402
[ ] User can create 2nd listing with plan_id
[ ] Admin can list pending listings
[ ] Admin can approve listing
[ ] Admin can reject listing
[ ] Approved listing visible in public list
```

---

## Environment Setup

### Local Development
```
base_url = http://localhost:8000
```

### Staging
```
base_url = https://staging.96sooq.com
```

### Production
```
base_url = https://api.96sooq.com
```

---

## Next Steps

1. **Import collection** into Postman
2. **Set base_url** environment variable
3. **Run Admin Login** to get admin token
4. **Create categories** with attributes
5. **Run OAuth flow** to get customer token
6. **Test listing creation** (free + paid)
7. **Test admin approval** workflow

---

## Support

For issues or questions:
- Check request descriptions in Postman
- Review `COMPLETE_GUIDE.md` for detailed API docs
- Check `PAYMENT_APPROVAL_FLOW.md` for payment logic
- Verify environment variables are set correctly

**Happy Testing!** 🚀
