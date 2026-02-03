# 96sooq Backend - Complete Integration Guide

## Table of Contents
1. [Overview](#overview)
2. [Database Schema](#database-schema)
3. [Authentication Flow](#authentication-flow)
4. [Admin Panel Integration](#admin-panel-integration)
5. [User App Integration](#user-app-integration)
6. [API Reference](#api-reference)
7. [Postman Collection](#postman-collection)

---

## Overview

96sooq is an OLX/Dubizzle-like marketplace platform with:
- **Hierarchical categories** with dynamic attributes
- **OAuth authentication** (Google, Apple, Facebook) + Phone OTP
- **Stores & Listings** with approval workflow
- **Admin panel** for content moderation

**Tech Stack:**
- Backend: FastAPI (Python)
- Database: Supabase (PostgreSQL)
- Authentication: JWT tokens

---

## Database Schema

### Core Tables

#### 1. app_users (Customers)
```sql
- id (UUID, PK)
- provider (TEXT) -- 'phone', 'google', 'apple', 'facebook'
- provider_id (TEXT) -- Unique ID from OAuth provider
- email (TEXT)
- phone_number (TEXT)
- name (TEXT)
- profile_picture (TEXT)
- otp (TEXT) -- For phone authentication
- is_active (BOOLEAN)
- created_at, updated_at
```

#### 2. users (Admins)
```sql
- id (UUID, PK)
- name, email, hashed_password
- created_at, updated_at
```

#### 3. categories (Hierarchical)
```sql
- id (UUID, PK)
- name_en, name_ar (TEXT)
- image_url (TEXT)
- parent_id (UUID, FK → categories.id)  -- NULL = root category
- attributes_schema (JSONB)  -- Dynamic fields definition
- is_active (BOOLEAN)
- created_at, updated_at
```

**attributes_schema Example:**
```json
[
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
```

#### 4. stores
```sql
- id (UUID, PK)
- user_id (UUID, FK → app_users.id)
- name, description (TEXT)
- logo_url, cover_image_url (TEXT)
- status (TEXT) -- 'pending_approval', 'active', 'rejected'
- plan_id (UUID, FK → pricing_plans.id)
- plan_expires_at (TIMESTAMP)
- rejection_reason (TEXT)
- created_at, updated_at
```

#### 5. listings
```sql
- id (UUID, PK)
- user_id (UUID, FK → app_users.id)
- category_id (UUID, FK → categories.id)
- store_id (UUID, FK → stores.id, nullable)
- title, description (TEXT)
- price (NUMERIC), currency (TEXT)
- status (TEXT) -- 'pending_approval', 'active', 'rejected', 'expired'
- plan_id (UUID, FK → pricing_plans.id)
- plan_expires_at (TIMESTAMP)
- attributes_values (JSONB)  -- User's answers to category attributes
- location (JSONB)  -- {lat, lng, address}
- rejection_reason (TEXT)
- created_at, updated_at
```

**attributes_values Example:**
```json
{
  "fuel_type": "Petrol",
  "year": 2020,
  "transmission": "Automatic",
  "mileage": 35000
}
```

#### 6. listing_images
```sql
- id (UUID, PK)
- listing_id (UUID, FK → listings.id)
- image_url (TEXT)
- is_main (BOOLEAN)
- display_order (INTEGER)
```

#### 7. pricing_plans
```sql
- id (UUID, PK)
- name (TEXT)
- type (TEXT) -- 'listing', 'store', 'banner'
- duration_days (INTEGER)
- price (NUMERIC)
- features (JSONB)
- is_active (BOOLEAN)
```

---

## Authentication Flow

### OAuth Sign-In (Google/Apple/Facebook)

**Two-Step Process:**

#### Step 1: Check If User Exists

```
User clicks "Sign in with Google"
  ↓
Frontend handles Google OAuth (gets provider_id, email)
  ↓
Frontend → POST /api/auth/oauth/check-user
```

**Request:**
```json
{
  "provider": "google",
  "provider_id": "google_user_123456",
  "email": "user@gmail.com"
}
```

**Response (Existing User):**
```json
{
  "exists": true,
  "access_token": "eyJhbGciOiJI...",
  "token_type": "bearer",
  "user": {
    "id": "usr_123",
    "name": "Ahmed Ali",
    "email": "user@gmail.com",
    "phone_number": "+971501234567"
  }
}
```

**Response (New User):**
```json
{
  "exists": false,
  "email": "user@gmail.com"
}
```

#### Step 2: Complete Profile (New Users)

If `exists = false`, frontend shows form asking for:
- Name (required)
- Phone Number (required)

```
Frontend → POST /api/auth/oauth/complete-profile
```

**Request:**
```json
{
  "provider": "google",
  "provider_id": "google_user_123456",
  "email": "user@gmail.com",
  "name": "Ahmed Ali",
  "phone_number": "+971501234567",
  "profile_picture": "https://..."
}
```

**Response:**
```json
{
  "id": "usr_456",
  "name": "Ahmed Ali",
  "phone_number": "+971501234567",
  "access_token": "eyJhbGciOiJI...",
  "token_type": "bearer"
}
```

### Phone OTP (Legacy - Still Supported)

1. `POST /api/auth/send-otp` → Send OTP to phone
2. `POST /api/auth/verify-otp` → Verify OTP, get token
3. `POST /api/auth/create-user` → Set name (optional)

---

## Admin Panel Integration

### 1. Creating Category Hierarchy

**Step 1: Create Root Category**

```http
POST /api/admin/categories/
Authorization: Bearer <admin_token>

{
  "name": "Vehicles",
  "image_url": "https://cdn.example.com/vehicles.png",
  "is_active": true
}

Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",  ← SAVE THIS!
  "name_en": "Vehicles",
  "name_ar": "مركبات",
  "parent_id": null,
  "is_active": true
}
```

**Step 2: Create Sub-Category with Attributes**

```http
POST /api/admin/categories/
Authorization: Bearer <admin_token>

{
  "name": "Cars",
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://cdn.example.com/cars.png",
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
    },
    {
      "key": "transmission",
      "label_en": "Transmission",
      "type": "select",
      "required": true,
      "options": ["Automatic", "Manual"]
    }
  ]
}

Response:
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "name_en": "Cars",
  "parent_id": "550e8400...",
  "attributes_schema": [...]
}
```

### 2. Managing Approvals

**List Pending Listings:**
```http
GET /api/admin/listings/?status=pending_approval
Authorization: Bearer <admin_token>

Response: Array of listings
```

**Approve Listing:**
```http
PUT /api/admin/listings/{listing_id}/approve
Authorization: Bearer <admin_token>
```

**Reject Listing:**
```http
PUT /api/admin/listings/{listing_id}/reject?reason=Inappropriate%20content
Authorization: Bearer <admin_token>
```

**Same for Stores (Manual Override):**
- `PUT /api/admin/stores/{store_id}/approve` (Re-activate)
- `PUT /api/admin/stores/{store_id}/reject` (Suspend)

---

## User App Integration

### 1. User Login Flow

```javascript
// Step 1: User clicks "Sign in with Google"
const googleUser = await googleSignIn();

// Step 2: Check if user exists
const checkResponse = await fetch('/api/auth/oauth/check-user', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    provider: 'google',
    provider_id: googleUser.sub,
    email: googleUser.email
  })
});

const data = await checkResponse.json();

if (data.exists) {
  // Login user
  localStorage.setItem('access_token', data.access_token);
  redirectToDashboard();
} else {
  // Show profile completion form
  showForm({
    email: data.email,
    onSubmit: (formData) => completeProfile(googleUser, formData)
  });
}

// Step 3: Complete profile (if new user)
async function completeProfile(googleUser, formData) {
  const response = await fetch('/api/auth/oauth/complete-profile', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      provider: 'google',
      provider_id: googleUser.sub,
      email: googleUser.email,
      name: formData.name,
      phone_number: formData.phone_number,
      profile_picture: googleUser.picture
    })
  });
  
  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);
  redirectToDashboard();
}
```

### 2. Creating a Listing (Dropdown Flow)

```javascript
// Step 1: Load root categories
async function loadCategories() {
  const categories = await fetch('/api/categories/');
  return categories.json();
}

// Step 2: On category select, load sub-categories
async function onCategorySelect(categoryId) {
  const subCategories = await fetch(`/api/categories/?parent_id=${categoryId}`);
  const data = await subCategories.json();
  
  if (data.length > 0) {
    // Has sub-categories - show dropdown
    populateSubCategoryDropdown(data);
  } else {
    // No sub-categories - check if leaf
    checkIfLeafAndLoadFields(categoryId);
  }
}

// Step 3: Check if leaf category and load dynamic fields
async function checkIfLeafAndLoadFields(categoryId) {
  const leafCheck = await fetch(`/api/categories/${categoryId}/is-leaf`);
  const { is_leaf } = await leafCheck.json();
  
  if (is_leaf) {
    // Get category details with attributes_schema
    const category = await fetch(`/api/categories/${categoryId}`);
    const data = await category.json();
    
    // Build dynamic form
    buildDynamicForm(data.attributes_schema);
    showListingForm();
  }
}

// Step 4: Build form dynamically
function buildDynamicForm(attributesSchema) {
  if (!attributesSchema) return;
  
  attributesSchema.forEach(field => {
    if (field.type === 'select') {
      createDropdownField(field);
    } else if (field.type === 'number') {
      createNumberField(field);
    } else if (field.type === 'text') {
      createTextField(field);
    }
  });
}

// Step 5: Submit listing
async function submitListing(formData, selectedCategoryId) {
  const response = await fetch('/api/listings/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      category_id: selectedCategoryId,
      title: formData.title,
      description: formData.description,
      price: formData.price,
      currency: 'AED',
      attributes_values: {
        fuel_type: formData.fuel_type,
        year: formData.year,
        transmission: formData.transmission
      },
      images: formData.uploadedImages,
      location: formData.location
    })
  });
  
  const data = await response.json();
  showMessage('Listing submitted for approval!');
}
```

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/oauth/check-user` | None | Check if OAuth user exists |
| POST | `/api/auth/oauth/complete-profile` | None | Complete profile for new OAuth user |
| POST | `/api/auth/send-otp` | None | Send OTP to phone (legacy) |
| POST | `/api/auth/verify-otp` | None | Verify OTP (legacy) |
| POST | `/api/auth/create-user` | Customer | Update name (legacy) |

### Admin - Auth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/admin/signup` | None | Create admin account |
| POST | `/api/admin/login` | None | Admin login |
| POST | `/api/admin/change-password` | Admin | Change password |

### Categories - Public

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/categories/` | None | List root categories (or `?parent_id={id}` for sub-categories) |
| GET | `/api/categories/{id}/is-leaf` | None | Check if category is a leaf node |

### Categories - Admin

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/admin/categories/` | Admin | Create category |
| GET | `/api/admin/categories/` | Admin | List all categories |
| GET | `/api/admin/categories/{id}` | Admin | Get category details |
| PUT | `/api/admin/categories/{id}` | Admin | Update category |
| DELETE | `/api/admin/categories/{id}` | Admin | Delete category |

### Stores - User

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/stores/` | Customer | Create store |
| GET | `/api/stores/` | None | List active stores (or `?user_id={id}` for user's stores) |
| GET | `/api/stores/{id}` | None | Get store details |
| PUT | `/api/stores/{id}` | Customer | Update store (owner only) |

### Stores - Admin

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| PUT | `/api/admin/stores/{id}/approve` | Admin | Approve store |
| PUT | `/api/admin/stores/{id}/reject` | Admin | Reject store |

### Listings - User

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/listings/` | Customer | Create listing |
| GET | `/api/listings/` | None | List active listings (filters: `?category_id=`, `?store_id=`, `?search=`) |
| GET | `/api/listings/{id}` | None | Get listing details |
| PUT | `/api/listings/{id}` | Customer | Update listing (owner only) |

### Listings - Admin

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/admin/listings/` | Admin | List all listings (filter: `?status=pending_approval`) |
| PUT | `/api/admin/listings/{id}/approve` | Admin | Approve listing |
| PUT | `/api/admin/listings/{id}/reject?reason=...` | Admin | Reject listing |

---

## Postman Collection

Import `96sooq_api.postman_collection.json` for all endpoints with examples.

**Environment Variables:**
```
base_url = http://localhost:8000
admin_token = <JWT from admin login>
customer_token = <JWT from OAuth or OTP>
```

---

## Key Concepts

### 1. Hierarchical Categories
- Use `parent_id` to create hierarchy
- Root categories have `parent_id = null`
- Check `is-leaf` endpoint before allowing listings

### 2. Dynamic Attributes
- Admin defines `attributes_schema` in category
- User fills `attributes_values` in listing
- Frontend dynamically builds form based on schema

### 3. Approval Workflow
- Listings start as `pending_approval`
- **Stores are auto-approved** (status = `active`)
- Admin uses `/approve` or `/reject` endpoints
- Only `active` items are visible to public

### 4. Authentication
- **OAuth**: Two-step (check-user → complete-profile for new users)
- **Phone OTP**: Three-step (send-otp → verify-otp → create-user)
- JWT tokens for all authenticated requests

---

## Example: Complete Category → Listing Flow

```
ADMIN CREATES:
1. Vehicles (root, id: A)
2. Cars (parent_id: A, id: B, attributes: fuel_type, year)

USER CREATES LISTING:
1. Selects "Vehicles" → Loads sub-categories
2. Selects "Cars" → Checks is-leaf (true)
3. Fetches Cars details → Gets attributes_schema
4. Form shows: Title, Price, Description, Fuel Type, Year
5. User fills and submits
6. Listing created with status: pending_approval
7. Admin approves
8. Listing becomes active and visible
```

---

## Next Steps

1. **Run OAuth migration**: Execute `backend/db/oauth_migration.sql` in Supabase
2. **Import Postman collection**: `96sooq_api.postman_collection.json`
3. **Test flows**: Admin panel → Category creation → User listing
4. **Integrate frontend**: Use OAuth SDK + API calls as documented

---

## Support

For questions or issues, refer to:
- API responses for detailed error messages
- Postman collection for working examples
- This document for complete integration flow
