# Individual User Workflow

This document outlines the step-by-step API calls required for an Individual User (C2C) to use the 96Sooq platform.

## 1. Authentication

### Step 1.1: Check if User Exists
**Endpoint:** `POST /api/auth/oauth/check-user`
*   **Purpose:** Initial check during login/signup to see if the user is already registered.
*   **Request:**
    ```json
    {
      "email": "user@example.com",
      "phone_number": "+96812345678"
    }
    ```
*   **Response:** `{"exists": true/false}`

### Step 1.2: Complete Profile (Register)
**Endpoint:** `POST /api/auth/oauth/complete-profile`
*   **Purpose:** Register a new user and get an access token.
*   **Request:**
    ```json
    {
      "email": "user@example.com",
      "phone_number": "+96812345678",
      "name": "Ali Al-Harthy",
      "uid": "FIREBASE_UID_123"
    }
    ```
*   **Response:** `{"access_token": "...", "token_type": "bearer", "user": {...}}`
*   **Next:** Save `access_token` for all subsequent authenticated requests.

---

## 2. Browsing & Preparation

### Step 2.1: Fetch Governorates (States)
**Endpoint:** `GET /api/locations/?type=state&is_active=true`
*   **Purpose:** Populate the first dropdown for location selection.
*   **Response:** List of Governorates (e.g., Muscat, Dhofar). Save `id` as `gov_id`.

### Step 2.2: Fetch Wilayats (Cities)
**Endpoint:** `GET /api/locations/?type=city&parent_id={gov_id}`
*   **Purpose:** Populate the second dropdown based on the selected Governorate.
*   **Response:** List of Wilayats (e.g., Seeb, Bawshar). Save `id` as `place_id` (this is the City ID).

### Step 2.3: Browse Categories
**Endpoint:** `GET /api/categories/?parent_id=root` (and drill down)
*   **Purpose:** Select a category for the listing (e.g., Motors -> Cars -> Toyota).
*   **Check:** Ensure `is_leaf` is `true` before allowing listing creation.

---

## 3. Creating a Listing

### Step 3.1: Check Quota & Plans
**Endpoint:** `GET /api/subscriptions/listing-prices?is_store=false`
*   **Purpose:** Determine if the user can create a free listing or needs to pay.
*   **Response:**
    *   `quota_status`: `can_create_free` (True/False), `usage` (Used/Max).
    *   `plans`: List of available individual plans (if payment needed).

### Step 3.2: Purchase a Plan (If Quota Exceeded)
**Endpoint:** `POST /api/subscriptions/purchase` (Optional)
*   **Condition:** Only if Step 3.1 returns `can_create_free: false` and `can_create_paid: false`.
*   **Request:** `{"plan_id": "{PLAN_ID}"}`
*   **Loophole Check needed:** Ensure user cannot bypass payment if quota is full. (Backend enforces this).

### Step 3.3: Upload Images
**Endpoint:** `POST /api/storage/presigned-url/upload`
*   **Purpose:** Get URLs to upload images to S3.
*   **Request:** `{"file_name": "car.jpg", "folder": "listings"}`
*   **Response:** `{"upload_url": "...", "public_url": "..."}`.
*   **Action:** Frontend uploads file to `upload_url`, sends `public_url` in Step 3.4.

### Step 3.4: Create the Listing
**Endpoint:** `POST /api/listings/`
*   **Purpose:** The final submission.
*   **Request:**
    ```json
    {
      "title": "Toyota Camry 2023",
      "description": "Mint condition, lady driven",
      "price": 7500,
      "currency": "OMR",
      "condition": "used",
      "category_id": "{CATEGORY_ID}",
      "location_id": "{GOV_ID}",  // From Step 2.1
      "place_id": "{CITY_ID}",     // From Step 2.2
      "images": ["https://s3.../img1.jpg"],
      "attributes_values": {"Year": "2023", "Kilometers": "20000"}
    }
    ```
*   **Validation:** Backend checks categories, locations, and quota again.
*   **Loophole Check:** Backend ignores `status` field in payload (always defaults to `pending_approval`).

---

## 4. Managing Listings

### Step 4.1: View My Listings
**Endpoint:** `GET /api/listings/?user_id={CURRENT_USER_ID}` (Need to implement filter or use `my-listings` endpoint equivalent)
*   **Note:** Currently `GET /api/listings/` is public. We should use `GET /api/listings/?user_id=...` but ensure draft/pending listings are visible to owner.

### Step 4.2: Edit Listing
**Endpoint:** `PUT /api/listings/{id}`
*   **Request:** Fields to update (e.g., price).
*   **security:** Backend resets status to `pending_approval` on sensitive edits (Price, Title, Desc) to prevent "Bait and Switch" fraud.

### Step 4.3: Boost Listing (Ad)
**Endpoint:** `POST /api/banners/boost`
*   **Purpose:** Promote an existing listing.
*   **Request:** `{"listing_id": "...", "plan_id": "..."}` (Requires Ad Plan).

---

## 5. Potential Loopholes & Security Checks

1.  **Quota Bypass:** User tries to hit `create_listing` repeatedly without a plan.
    *   *Fix:* Backend `create_listing` checks `user_subscriptions` table before insert.
2.  **Location Spoofing:** Sending random strings as `location_id`.
    *   *Fix:* Backend validates `location_id` against `locations` table (must be `type='state'`).
3.  **City Mismatch:** Sending a Muscat City ID with a Dhofar Governorate ID.
    *   *Fix:* Backend validates `city.parent_id == location_id`.
4.  **Edit Fraud:** Changing a "Pen" listing to a "Car" after approval.
    *   *Fix:* Backend reverts status to `pending_approval` upon edit.
