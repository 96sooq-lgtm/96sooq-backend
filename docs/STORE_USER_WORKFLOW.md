# Store User Workflow

This document outlines the step-by-step API calls required for a Store User (B2C) to register a business and sell products on the 96Sooq platform.

## 1. Authentication

### Step 1.1: Authentication (Same as Individual)
**Endpoint:** `POST /api/auth/oauth/check-user`
**Endpoint:** `POST /api/auth/oauth/complete-profile`
*   **Purpose:** Store user also has a normal account first, then upgrades to Store.

---

## 2. Store Creation

### Step 2.1: View Store Plans
**Endpoint:** `GET /api/subscriptions/listing-prices?is_store=true`
*   **Purpose:** Choose a plan for opening a store.
*   **Response:** List of Store Plans (e.g., Bronze, Silver, Gold). Save `id` as `plan_id`.

### Step 2.2: Fetch Governorates (States)
**Endpoint:** `GET /api/locations/?type=state&is_active=true`
*   **Purpose:** Select where the physical shop is located.
*   **Response:** Save `id` as `location_id`.

### Step 2.3: Fetch Wilayats (Cities)
**Endpoint:** `GET /api/locations/?type=city&parent_id={location_id}`
*   **Purpose:** Select shop city.
*   **Response:** Save `id` as `place_id`.

### Step 2.4: Create Store (Upgrade)
**Endpoint:** `POST /api/stores/`
*   **Purpose:** Register the business.
*   **Request:**
    ```json
    {
      "name_en": "Ahmed Electronics",
      "name_ar": "إلكترونيات أحمد",
      "description": "Authorized Samsung Reseller",
      "location_id": "{GOV_ID}",  // From 2.2
      "place_id": "{CITY_ID}",     // From 2.3
      "plan_id": "{PLAN_ID}",      // From 2.1
      "logo_url": "https://s3.../logo.png"
    }
    ```
*   **Validation:** Backend checks valid `location_id`, `place_id`, and `plan_id`.
*   **Loophole Check:** `status` is set to `active` (auto-approve per request) or `pending_approval` based on global policy.

---

## 3. Store Management

### Step 3.1: View My Store Details
**Endpoint:** `GET /api/stores/?user_id=current` Or `GET /api/stores/{id}`
*   **Purpose:** Get `store_id` (important for listings).

### Step 3.2: Update Store Profile
**Endpoint:** `PUT /api/stores/{store_id}`
*   **Purpose:** Change details like description or banner.
*   **Request:**
    ```json
    {
      "description": "We now sell TVs too!", 
      "cover_image_url": "https://s3.../banner.jpg" 
    }
    ```

---

## 4. Creating Store Listings

### Step 4.1: Store Listing Quota
*   **Note:** Store Plan dictates quota. The method is slightly different. Store users typically have larger quotas.
*   **Validation:** `create_listing` automatically checks against `store_subscriptions` (implementation pending or merged with user_subscriptions logic for simplicity).

### Step 4.2: Create Listing (Linked to Store)
**Endpoint:** `POST /api/listings/`
*   **Request:**
    ```json
    {
      "title": "Samsung S24 Ultra",
      "price": 450,
      "condition": "new",
      "category_id": "{CATEGORY_ID}",
      "location_id": "{GOV_ID}", 
      "place_id": "{CITY_ID}", 
      "images": ["url1", "url2"],
      "attributes_values": {"Color": "Black", "Storage": "512GB"}
    }
    ```
*   **Backend Logic:**
    1.  Checks if current user owns an active store.
    2.  If yes, `store_id` is automatically set to user's store ID.
    3.  `status` set to `pending_approval`? (Or `active` if store is trusted/verified). *Currently defaulting to pending*.

---

## 5. Potential Loopholes & Security Checks (Store)

1.  **Multiple Stores:** User creates 5 stores to get free trials.
    *   *Fix:* Backend restricts 1 Store per User (unless upgraded to "Enterprise"). Check `stores` table for `user_id` before creating new one.
2.  **Fake Location:** Setting `place_id` to a city not in `location_id` governorate.
    *   *Fix:* Backend enforces `place.parent_id == location_id`.
3.  **Unlimited Listings:** Store plan might have limit.
    *   *Fix:* Backend checks remaining quota in `store_subscriptions` before insert.
4.  **Impersonation:** User tries to create listing for another store by sending `store_id` in payload.
    *   *Fix:* Backend ignores `store_id` from payload for normal users. It *derives* `store_id` from the logged-in user's `stores` record.
