# 📱 Complete Flutter API Integration Guide

This document describes the complete integration flow for the 96sooq Mobile App and Admin Panel. It covers every implemented feature from Admin setup to User Listing creation.

## 🌍 Base Configuration

- **Base URL:** `http://localhost:8000` (Change for Staging/Prod)
- **Headers:**
  - `Content-Type`: `application/json`
  - `Authorization`: `Bearer <token>` (Required for protected endpoints)

---

## 🛠️ Module 1: Admin Panel Integration

Before users can do anything, an Admin must set up the platform (Categories).

### 1.1 Admin Authentication

#### Sign Up (First time only)
- **Screen:** Admin Registration
- **API:** `POST /api/admin/signup`
- **Body:** `{ "name": "Admin", "email": "admin@96sooq.com", "password": "..." }`

#### Login
- **Screen:** Admin Login
- **API:** `POST /api/admin/login`
- **Body:** `{ "email": "admin@96sooq.com", "password": "..." }`
- **Action:** Save `access_token` securely. Use this token for all "Module 1" requests.

### 1.2 Category Management (The Backbone)

The app relies on a hierarchy: `Vehicles` -> `Cars` -> `Toyota`.

#### Step A: Create Root Category
- **Screen:** Add Category
- **API:** `POST /api/admin/categories/`
- **Body:** `{ "name": "Vehicles", "image_url": "..." }`
- **Response:** Returns `id` (e.g., `CAT_ID_1`). **Save this.**

#### Step B: Create Sub-Category with Dynamic Attributes
This is where you define what fields a user sees when listing a car.

- **Screen:** Add Sub-Category (e.g., "Cars")
- **API:** `POST /api/admin/categories/`
- **Body:**
  ```json
  {
    "name": "Cars",
    "parent_id": "CAT_ID_1",  // Link to Vehicles
    "image_url": "...",
    "attributes_schema": [    // 👈 IMPORTANT: Defines the Dynamic Form
      {
        "key": "fuel_type",
        "label_en": "Fuel Type",
        "type": "select",
        "required": true,
        "options": ["Petrol", "Diesel", "Electric"]
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
- **Response:** Returns `id` (e.g., `CAT_ID_CARS`).

---

## 👤 Module 2: User Authentication (Social Login)

We use a "Check-first" approach for Google/Apple/Facebook.

### 2.1 The Flow

1.  **User Clicks "Sign in with Google":**
    - Flutter App gets `google_token`, `email`, and `provider_id` from Google SDK.

2.  **Check Registration:**
    - **API:** `POST /api/auth/oauth/check-user`
    - **Body:** `{ "provider": "google", "provider_id": "...", "email": "..." }`
    
    **Result A: User Exists (`exists: true`)**
    - You get `access_token`. Login successful. Redirect to Home.
    
    **Result B: New User (`exists: false`)**
    - Redirect to **Complete Profile Screen**.

3.  **Complete Profile (If New):**
    - **Screen:** User enters Name and Phone.
    - **API:** `POST /api/auth/oauth/complete-profile`
    - **Body:** `{ "provider": "...", "email": "...", "name": "Ali", "phone_number": "+971..." }`
    - **Response:** You get `access_token`. Login successful.

---

## 🛍️ Module 3: Marketplace (User Flow)

### 3.1 Browsing & Navigation

#### Home Screen
Show top-level categories.
- **API:** `GET /api/categories/` (Root categories only)

#### Sub-Category Screen
When user taps "Vehicles":
- **API:** `GET /api/categories/?parent_id={VEHICLES_ID}`
- **Logic:**
  - If detailed list returns: Show list.
  - If list empty: This is a "Leaf" category (navigating deeper is done).

### 3.2 Creating a Store (Optional for User)

- **Screen:** "Become a Seller" / "Create Store"
- **API:** `POST /api/stores/`
- **Body:** `{ "name": "Ali Motors", "description": "...", "logo_url": "..." }`
- **Note:** Status will be `active` immediately upon creation.

### 3.3 Creating a Listing (Core Feature)

This is the most critical flow in the app.

#### Step 1: Select Category Logic
User selects `Vehicles` -> `Cars`.
Check if `Cars` allows listing (Is it a leaf?):
- **API:** `GET /api/categories/{CARS_ID}/is-leaf`
- If `true`: Proceed to form.
- If `false`: Show sub-categories (e.g., Toyota, Honda).

#### Step 2: Build Dynamic Form 🎨
Fetch the schema to know what fields to show.
- **API:** `GET /api/categories/{CARS_ID}`
- **Response `attributes_schema`:**
  ```json
  [ { "key": "fuel_type", "type": "select", "options": [...] }, ... ]
  ```
- **Flutter Logic:**
  - Iterate through schema.
  - If `type == "select"` -> Render `Dropdown`.
  - If `type == "number"` -> Render `TextField(keyboard: number)`.
  - Collect user answers into a map: `{"fuel_type": "Petrol", "year": 2020}`.

#### Step 3: Payment Check (First Free) 💳
Before submitting:
1.  Check user's existing listings: `GET /api/listings/?user_id={ME}`.
2.  **If Count == 0:** First one is **Free**. `plan_id = null`.
3.  **If Count > 0:** **Paywall**.
    - Show Pricing Plans.
    - User pays via Stripe/Apple Pay.
    - Get `plan_id` (e.g., "PLAN_PREMIUM").

#### Step 4: Submit Listing
- **API:** `POST /api/listings/`
- **Body:**
  ```json
  {
    "category_id": "CARS_ID",
    "title": "My Car",
    "price": 50000,
    "description": "...",
    "plan_id": null,       // or "PLAN_ID" if paid
    "attributes_values": { // Answers from Step 2
      "fuel_type": "Petrol",
      "year": 2020
    },
    "images": ["url1", "url2"],
    "location": { "lat": 25.1, "lng": 55.2 }
  }
  ```
- **Response:** `201 Created`. Status is `pending_approval`.

---

## 👮 Module 4: Admin Approval Workflow

Admin needs a dashboard to approve listings.

### 4.1 Approving Listings
- **List:** `GET /api/admin/listings/?status=pending_approval`
- **Detail:** Show images, attributes (`fuel_type`, etc).
- **Approve:** `PUT /api/admin/listings/{LISTING_ID}/approve`
- **Reject:** `PUT /api/admin/listings/{LISTING_ID}/reject?reason=Bad+Images`

---

## 🎯 Summary of Developer Tasks

1.  **Auth:** Implement Google Sign-In + `check-user`/`complete-profile` logic.
2.  **Home:** Recursively navigate categories using `parent_id`.
3.  **Posting:** Create a dynamic form builder widget that takes `attributes_schema` input and produces UI fields.
4.  **Payments:** Implement logic to count user listings and force payment for the 2nd one.
5.  **Admin:** Simple list views for Pending items with Approve/Reject buttons.
