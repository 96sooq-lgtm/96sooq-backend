# 96Sooq — Frontend API Integration Guide

> **Base URL:** `https://your-app.onrender.com`
> **Auth Header:** `Authorization: Bearer {access_token}` (required for all authenticated endpoints)

---

## 🔐 AUTHENTICATION (Both User Types)

### Step 1 — Check if User Exists
```
POST /api/auth/oauth/check-user
```
```json
{
  "email": "user@example.com",
  "phone_number": "+96812345678"
}
```
**Response:** `{ "exists": true }` or `{ "exists": false }`

---

### Step 2A — Login (User Exists)
```
POST /api/auth/oauth/complete-profile
```
```json
{
  "email": "user@example.com",
  "phone_number": "+96812345678",
  "name": "Ali Al-Harthy",
  "uid": "FIREBASE_UID_123"
}
```
**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "name": "Ali Al-Harthy",
    "email": "user@example.com",
    "phone_number": "+96812345678"
  }
}
```
> 💾 **Save `access_token`** — used in all subsequent requests.

---

## 🗺️ LOCATION & CATEGORY (Both User Types)

### Fetch Governorates (Dropdown 1)
```
GET /api/locations/?type=state&is_active=true
```
**Response:** `[{ "id": "uuid", "name_en": "Muscat", "name_ar": "مسقط" }]`
> 💾 Save selected `id` as `gov_id`

### Fetch Wilayats (Dropdown 2 — depends on Governorate)
```
GET /api/locations/?type=city&parent_id={gov_id}
```
**Response:** `[{ "id": "uuid", "name_en": "Seeb", "name_ar": "سيب" }]`
> 💾 Save selected `id` as `place_id`

### Fetch Categories
```
GET /api/categories/?parent_id=root
GET /api/categories/?parent_id={category_id}   ← drill down
```
**Response:** `[{ "id": "uuid", "name_en": "Motors", "is_leaf": false }]`
> ⚠️ Only allow listing creation when `is_leaf: true`

---

---

# 👤 INDIVIDUAL USER FLOW

## FLOW A — Create a Listing (Free / Paid)

### Step 1 — Check Quota & Available Plans
```
GET /api/subscriptions/listing-prices?is_store=false
Authorization: Bearer {token}
```
**Response:**
```json
{
  "quota_status": {
    "can_create_free": true,
    "usage": "0/1",
    "remaining": 1
  },
  "plans": [
    { "id": "uuid", "name_en": "Basic", "price": 0, "quota": 1 },
    { "id": "uuid", "name_en": "Premium", "price": 5.0, "quota": 5 }
  ]
}
```

### Step 2 — Upload Images (Optional but Recommended)
```
POST /api/storage/presigned-url/upload
Authorization: Bearer {token}
```
```json
{ "file_name": "car.jpg", "folder": "listings" }
```
**Response:** `{ "upload_url": "https://s3...", "public_url": "https://cdn..." }`
> Upload file to `upload_url` via PUT, then use `public_url` in listing creation.

### Step 3 — Create Listing (Draft)
```
POST /api/listings/
Authorization: Bearer {token}
```
```json
{
  "title": "Toyota Camry 2023",
  "description": "Mint condition, lady driven",
  "price": 7500,
  "currency": "OMR",
  "condition": "used",
  "category_id": "{LEAF_CATEGORY_ID}",
  "location_id": "{GOV_ID}",
  "place_id": "{PLACE_ID}",
  "images": ["https://cdn.../img1.jpg", "https://cdn.../img2.jpg"],
  "attributes_values": {
    "Year": "2023",
    "Kilometers": "20000",
    "Color": "White"
  }
}
```
**Response:**
```json
{
  "id": "listing-uuid",
  "status": "draft",
  "title": "Toyota Camry 2023"
}
```
> 💾 Save `listing_id` for checkout.

### Step 4 — Checkout (Initiate Payment or Free Activation)
```
POST /api/payments/checkout
Authorization: Bearer {token}
```
```json
{
  "listing_id": "{LISTING_ID}",
  "listing_plan_id": "{PLAN_ID}",
  "ad_plan_id": null,
  "currency": "OMR"
}
```

**Response A — Free (Quota Available):**
```json
{
  "status": "success",
  "transaction_id": "txn-uuid",
  "message": "Order processed successfully. Listing is under review."
}
```
> ✅ Show "Listing submitted for review" screen. Done.

**Response B — Paid:**
```json
{
  "status": "payment_initiated",
  "transaction_id": "txn-uuid",
  "payment_url": "https://oman.paymob.com/unifiedcheckout/?publicKey=...&clientSecret=..."
}
```
> 💾 Save `transaction_id`. Open `payment_url` in WebView.

### Step 5 — Poll Payment Status (After WebView)
```
GET /api/payments/payment-check?transaction_id={TXN_ID}
Authorization: Bearer {token}
```
**Response:**
```json
{
  "transaction_id": "txn-uuid",
  "status": "success",       ← pending | success | failed | cancelled
  "amount": 5.0,
  "currency": "OMR",
  "listing_id": "listing-uuid"
}
```
> Poll every 3 seconds until `status != "pending"`.

### Step 6A — Payment Success Screen
```
GET /api/payments/payment-success?transaction_id={TXN_ID}
Authorization: Bearer {token}
```
**Response:**
```json
{
  "status": "success",
  "transaction_id": "txn-uuid",
  "amount": 5.0,
  "currency": "OMR",
  "listing_id": "listing-uuid",
  "message": "Payment successful! Your listing is under review by our team."
}
```

### Step 6B — Payment Cancelled
```
GET /api/payments/payment-cancel?transaction_id={TXN_ID}
Authorization: Bearer {token}
```
**Response:**
```json
{
  "status": "cancelled",
  "transaction_id": "txn-uuid",
  "message": "Payment was cancelled. Your listing was not submitted."
}
```

---

## FLOW B — Boost an Existing Listing (Add)

### Step 1 — Get Ad Plans
```
GET /api/subscriptions/ad-prices
Authorization: Bearer {token}
```
**Response:** `[{ "id": "uuid", "name_en": "Featured 7 Days", "price": 3.0 }]`

### Step 2 — Checkout with Ad Plan
```
POST /api/payments/checkout
Authorization: Bearer {token}
```
```json
{
  "listing_id": "{EXISTING_LISTING_ID}",
  "listing_plan_id": null,
  "ad_plan_id": "{AD_PLAN_ID}",
  "currency": "OMR"
}
```
> Same payment flow as above (Steps 4–6).

---

## FLOW C — Manage My Listings

### View My Listings
```
GET /api/listings/?user_id={MY_USER_ID}
Authorization: Bearer {token}
```

### Edit a Listing
```
PUT /api/listings/{listing_id}
Authorization: Bearer {token}
```
```json
{
  "price": 7000,
  "description": "Updated description"
}
```
> ⚠️ Editing price/title/description resets status to `pending_approval`.

---

---

# 🏪 STORE USER FLOW

## FLOW A — Create a Store

### Step 1 — Get Store Plans (Optional)
```
GET /api/subscriptions/listing-prices?is_store=true
Authorization: Bearer {token}
```

### Step 2 — Create Store
```
POST /api/stores/
Authorization: Bearer {token}
```
```json
{
  "name_en": "Al-Harthy Motors",
  "name_ar": "الحارثي للسيارات",
  "description": "Premium used cars in Muscat",
  "phone": "+96812345678",
  "whatsapp": "+96812345678",
  "email": "store@example.com",
  "location_id": "{GOV_ID}",
  "place_id": "{PLACE_ID}",
  "logo_url": "https://cdn.../logo.jpg",
  "cover_url": "https://cdn.../cover.jpg"
}
```
**Response:**
```json
{
  "id": "store-uuid",
  "name": "Al-Harthy Motors",
  "status": "pending_approval"
}
```
> 💾 Save `store_id`.

---

## FLOW B — Store Creates a Listing

### Step 1 — Check Store Quota
```
GET /api/subscriptions/listing-prices?is_store=true
Authorization: Bearer {token}
```

### Step 2 — Upload Images
Same as Individual User Step 2 above.

### Step 3 — Create Listing Under Store
```
POST /api/listings/
Authorization: Bearer {token}
```
```json
{
  "title": "Honda Accord 2022",
  "description": "Single owner, full service history",
  "price": 6500,
  "currency": "OMR",
  "condition": "used",
  "category_id": "{LEAF_CATEGORY_ID}",
  "location_id": "{GOV_ID}",
  "place_id": "{PLACE_ID}",
  "store_id": "{STORE_ID}",
  "images": ["https://cdn.../img1.jpg"],
  "attributes_values": { "Year": "2022", "Kilometers": "35000" }
}
```

### Step 4 — Checkout (Same as Individual)
```
POST /api/payments/checkout
Authorization: Bearer {token}
```
```json
{
  "listing_id": "{LISTING_ID}",
  "listing_plan_id": "{STORE_PLAN_ID}",
  "ad_plan_id": null,
  "currency": "OMR"
}
```

---

## FLOW C — Store Manages Listings

### View Store Listings
```
GET /api/listings/?store_id={STORE_ID}
```

### View Store Profile
```
GET /api/stores/{store_id}
```

### Update Store
```
PUT /api/stores/{store_id}
Authorization: Bearer {token}
```
```json
{
  "description": "Updated description",
  "phone": "+96899999999"
}
```

---

---

# 📋 COMPLETE API REFERENCE SUMMARY

| # | Method | Endpoint | Auth | Purpose |
|---|--------|----------|------|---------|
| 1 | POST | `/api/auth/oauth/check-user` | ❌ | Check if user exists |
| 2 | POST | `/api/auth/oauth/complete-profile` | ❌ | Register / Login |
| 3 | GET | `/api/locations/` | ❌ | Get Governorates / Wilayats |
| 4 | GET | `/api/categories/` | ❌ | Browse categories |
| 5 | GET | `/api/subscriptions/listing-prices` | ✅ | Check quota & plans |
| 6 | GET | `/api/subscriptions/ad-prices` | ✅ | Get ad boost plans |
| 7 | POST | `/api/storage/presigned-url/upload` | ✅ | Upload images to S3 |
| 8 | POST | `/api/listings/` | ✅ | Create listing (draft) |
| 9 | GET | `/api/listings/` | ❌ | Browse listings |
| 10 | PUT | `/api/listings/{id}` | ✅ | Edit listing |
| 11 | POST | `/api/payments/checkout` | ✅ | Initiate payment |
| 12 | GET | `/api/payments/payment-check` | ✅ | Poll payment status |
| 13 | GET | `/api/payments/payment-success` | ✅ | Thank you page data |
| 14 | GET | `/api/payments/payment-cancel` | ✅ | Cancel payment |
| 15 | POST | `/api/stores/` | ✅ | Create store |
| 16 | GET | `/api/stores/{id}` | ❌ | View store profile |
| 17 | PUT | `/api/stores/{id}` | ✅ | Update store |

---

## ⚠️ Important Notes for Frontend

1. **Draft → Pending:** Listing is created as `draft`. After successful payment (or free quota), it moves to `pending_approval`. Admin activates it to `active`.
2. **Payment Polling:** After WebView closes, poll `/payment-check` every 3 seconds (max 10 attempts) until status changes from `pending`.
3. **Token Storage:** Store `access_token` securely (Keychain on iOS, Keystore on Android).
4. **Image Upload:** Always upload images BEFORE creating the listing. Use the `public_url` from presigned URL response.
5. **Location Validation:** `place_id` must belong to the selected `location_id` (Governorate). Backend validates this.
