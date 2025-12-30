# CRUD Operations Documentation

This document outlines all the CRUD (Create, Read, Update, Delete) operations available in the 96sooq Backend API.

## Listings CRUD Operations

### Admin Endpoints (`/api/admin/listings`)

#### Create Listing
- **Endpoint**: `POST /api/admin/listings`
- **Description**: Create a new listing (admin only)
- **Request Body**:
```json
{
  "title": "iPhone 14 Pro",
  "description": "Excellent condition, like new",
  "category_id": "cat-123",
  "user_id": "user-456",
  "price": 899.99,
  "location": "Riyadh",
  "phone_number": "+966501234567",
  "image_url": "https://example.com/image.jpg",
  "is_active": true
}
```
- **Response**: Returns the created listing with `id`, `created_at`, `updated_at`

#### List All Listings (Admin)
- **Endpoint**: `GET /api/admin/listings?skip=0&limit=100`
- **Description**: List all listings with pagination (admin only)
- **Query Parameters**:
  - `skip` (default: 0): Number of records to skip
  - `limit` (default: 100, max: 500): Number of records to return
- **Response**: Array of listings

#### Get Specific Listing (Admin)
- **Endpoint**: `GET /api/admin/listings/{listing_id}`
- **Description**: Get a specific listing by ID (admin only)
- **Response**: Single listing object

#### Update Listing
- **Endpoint**: `PUT /api/admin/listings/{listing_id}`
- **Description**: Update a listing (all fields optional)
- **Request Body**:
```json
{
  "title": "Updated title",
  "price": 799.99,
  "location": "Jeddah"
}
```
- **Response**: Updated listing object

#### Delete Listing
- **Endpoint**: `DELETE /api/admin/listings/{listing_id}`
- **Description**: Delete a listing permanently
- **Response**: `{"message": "Listing deleted successfully", "id": "listing_id"}`

---

### Public Endpoints (`/api/listings`)

#### List Active Listings
- **Endpoint**: `GET /api/listings?skip=0&limit=100&category_id=cat-123&location=Riyadh`
- **Description**: List all active listings with optional filters
- **Query Parameters**:
  - `skip` (default: 0): Pagination offset
  - `limit` (default: 100, max: 500): Number of results
  - `category_id` (optional): Filter by category
  - `location` (optional): Filter by location
- **Response**: Array of active listings

#### Get Specific Listing (Public)
- **Endpoint**: `GET /api/listings/{listing_id}`
- **Description**: Get a specific active listing by ID
- **Response**: Single listing object (only if active)

---

### User Endpoints (`/api/user/listings`)

#### Create User Listing
- **Endpoint**: `POST /api/user/listings`
- **Description**: Create a new listing for authenticated user
- **Request Body**: Same as admin create
- **Response**: Created listing object

#### Get User's Listings
- **Endpoint**: `GET /api/user/listings/user/{user_id}?skip=0&limit=100`
- **Description**: Get all listings for a specific user
- **Query Parameters**:
  - `skip` (default: 0): Pagination offset
  - `limit` (default: 100): Number of results
- **Response**: Array of user's listings

#### Update User's Listing
- **Endpoint**: `PUT /api/user/listings/{listing_id}`
- **Description**: Update user's own listing
- **Request Body**: Same as admin update
- **Response**: Updated listing object

#### Delete User's Listing
- **Endpoint**: `DELETE /api/user/listings/{listing_id}`
- **Description**: Delete user's own listing
- **Response**: `{"message": "Listing deleted successfully", "id": "listing_id"}`

---

## User Management Endpoints

### Admin User Endpoints (`/api/admin/users`)

#### List All Users
- **Endpoint**: `GET /api/admin/users?skip=0&limit=100`
- **Description**: List all users with pagination (admin only)
- **Query Parameters**:
  - `skip` (default: 0): Pagination offset
  - `limit` (default: 100, max: 500): Number of results
- **Response**: Array of user objects (id, name, email only)

#### Get Specific User
- **Endpoint**: `GET /api/admin/users/{user_id}`
- **Description**: Get a specific user by ID (admin only)
- **Response**: User object with id, name, email

---

## Existing Authentication Endpoints

### Admin Authentication (`/api/admin`)

#### Sign Up
- **Endpoint**: `POST /api/admin/signup`
- **Request Body**:
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "SecurePass123"
}
```
- **Response**: User object (id, name, email)

#### Login
- **Endpoint**: `POST /api/admin/login`
- **Request Body**:
```json
{
  "email": "john@example.com",
  "password": "SecurePass123"
}
```
- **Response**: Success message with user object

#### Change Password
- **Endpoint**: `POST /api/admin/change-password`
- **Request Body**:
```json
{
  "email": "john@example.com",
  "new_password": "NewSecurePass456"
}
```
- **Response**: Success message

---

## Listing Object Structure

```json
{
  "id": "listing-123",
  "title": "iPhone 14 Pro",
  "description": "Excellent condition, like new",
  "category_id": "cat-123",
  "user_id": "user-456",
  "price": 899.99,
  "location": "Riyadh",
  "phone_number": "+966501234567",
  "image_url": "https://example.com/image.jpg",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

## User Object Structure

```json
{
  "id": "user-456",
  "name": "John Doe",
  "email": "john@example.com"
}
```

---

## Error Responses

All endpoints return appropriate HTTP status codes:

- **400 Bad Request**: Invalid input data
- **404 Not Found**: Resource not found
- **401 Unauthorized**: Authentication failed
- **500 Internal Server Error**: Server error

Example error response:
```json
{
  "detail": "Listing not found"
}
```

---

## Pagination

For endpoints that support pagination:
- Use `skip` parameter to offset results
- Use `limit` parameter to control page size (max 500)
- Example: `GET /api/admin/listings?skip=20&limit=50`

---

## Database Table Requirements

Ensure the following tables exist in Supabase:

### listings table
- id (UUID)
- title (TEXT)
- description (TEXT)
- category_id (UUID, FK)
- user_id (UUID, FK)
- price (DECIMAL)
- location (TEXT)
- phone_number (TEXT, optional)
- image_url (TEXT, optional)
- is_active (BOOLEAN)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

### users table
- id (UUID)
- name (TEXT)
- email (TEXT, unique)
- password_hash (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

### categories table
- id (UUID)
- name (TEXT, unique)
- is_active (BOOLEAN)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
