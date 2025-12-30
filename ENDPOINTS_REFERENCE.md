# Complete API Endpoints Reference

## All 14 Endpoints at a Glance

### Admin Listing Management (5 endpoints)

| # | Method | Endpoint | Description | Request Body | Response |
|---|--------|----------|-------------|--------------|----------|
| 1 | POST | `/api/admin/listings` | Create listing | ListingCreate | ListingOut (201) |
| 2 | GET | `/api/admin/listings?skip=0&limit=100` | List all listings | - | [ListingOut] (200) |
| 3 | GET | `/api/admin/listings/{listing_id}` | Get listing by ID | - | ListingOut (200) |
| 4 | PUT | `/api/admin/listings/{listing_id}` | Update listing | ListingUpdate | ListingOut (200) |
| 5 | DELETE | `/api/admin/listings/{listing_id}` | Delete listing | - | {message, id} (200) |

### Public Listing Browsing (2 endpoints)

| # | Method | Endpoint | Description | Query Params | Response |
|---|--------|----------|-------------|--------------|----------|
| 6 | GET | `/api/listings?skip=0&limit=100` | List active listings | category_id, location | [ListingOut] (200) |
| 7 | GET | `/api/listings/{listing_id}` | Get active listing by ID | - | ListingOut (200) |

### User Listing Management (4 endpoints)

| # | Method | Endpoint | Description | Request Body | Response |
|---|--------|----------|-------------|--------------|----------|
| 8 | POST | `/api/user/listings` | Create user listing | ListingCreate | ListingOut (201) |
| 9 | GET | `/api/user/listings/user/{user_id}?skip=0&limit=100` | Get user's listings | - | [ListingOut] (200) |
| 10 | PUT | `/api/user/listings/{listing_id}` | Update user listing | ListingUpdate | ListingOut (200) |
| 11 | DELETE | `/api/user/listings/{listing_id}` | Delete user listing | - | {message, id} (200) |

### User Management (2 endpoints)

| # | Method | Endpoint | Description | Query Params | Response |
|---|--------|----------|-------------|--------------|----------|
| 12 | GET | `/api/admin/users?skip=0&limit=100` | List all users | skip, limit | [UserOut] (200) |
| 13 | GET | `/api/admin/users/{user_id}` | Get user details | - | UserOut (200) |

### Bonus: Existing Auth Endpoints (3 endpoints)

| # | Method | Endpoint | Description | Request Body | Response |
|---|--------|----------|-------------|--------------|----------|
| 14 | POST | `/api/admin/signup` | Register user | UserCreate | UserOut (200) |
| 15 | POST | `/api/admin/login` | Login user | LoginRequest | {message, user} (200) |
| 16 | POST | `/api/admin/change-password` | Change password | ChangePasswordRequest | {message} (200) |

---

## Request/Response Models

### ListingCreate (Input)
```json
{
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "user_id": "uuid",
  "price": 0.0,
  "location": "string",
  "phone_number": "string (optional)",
  "image_url": "string (optional)",
  "is_active": true (optional, default=true)
}
```

### ListingUpdate (Input)
```json
{
  "title": "string (optional)",
  "description": "string (optional)",
  "category_id": "uuid (optional)",
  "price": 0.0 (optional),
  "location": "string (optional)",
  "phone_number": "string (optional)",
  "image_url": "string (optional)",
  "is_active": true (optional)
}
```

### ListingOut (Response)
```json
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "user_id": "uuid",
  "price": 0.0,
  "location": "string",
  "phone_number": "string or null",
  "image_url": "string or null",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### UserOut (Response)
```json
{
  "id": "uuid",
  "name": "string",
  "email": "string"
}
```

---

## Query Parameters

### Pagination
- **skip**: Integer (default: 0, min: 0)
  - Number of records to skip
  - Example: `skip=20` skips first 20 records

- **limit**: Integer (default: 100, min: 1, max: 500)
  - Maximum records to return
  - Example: `limit=50` returns max 50 records

### Filters (Public Listings Only)
- **category_id**: UUID (optional)
  - Filter listings by category
  - Example: `category_id=12345678-1234-1234-1234-123456789012`

- **location**: String (optional)
  - Filter listings by location
  - Example: `location=Riyadh`

### Examples
```
/api/listings?skip=0&limit=20
/api/listings?skip=20&limit=20
/api/listings?category_id=cat-123&location=Riyadh
/api/listings?category_id=cat-123&location=Riyadh&skip=0&limit=50
/api/admin/users?skip=0&limit=100
/api/user/listings/user/{user_id}?skip=0&limit=20
```

---

## HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Request successful, returning data |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid input, missing fields, or invalid data |
| 401 | Unauthorized | Authentication failed |
| 404 | Not Found | Resource (listing, user, category) not found |
| 500 | Internal Server Error | Server/database error |

---

## Error Responses

All errors follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Examples

**400 Bad Request - Missing field**
```json
{
  "detail": "Field 'title' is required"
}
```

**400 Bad Request - Invalid data**
```json
{
  "detail": "Price must be greater than 0"
}
```

**404 Not Found - Listing**
```json
{
  "detail": "Listing not found"
}
```

**404 Not Found - Category**
```json
{
  "detail": "Category not found"
}
```

**404 Not Found - User**
```json
{
  "detail": "User not found"
}
```

**500 Server Error**
```json
{
  "detail": "Failed to create listing"
}
```

---

## CURL Examples

### Create Listing
```bash
curl -X POST http://localhost:8000/api/admin/listings \
  -H "Content-Type: application/json" \
  -d '{
    "title": "iPhone 14 Pro",
    "description": "Excellent condition",
    "category_id": "12345678-1234-1234-1234-123456789012",
    "user_id": "87654321-4321-4321-4321-210987654321",
    "price": 899.99,
    "location": "Riyadh",
    "phone_number": "+966501234567",
    "image_url": "https://example.com/image.jpg"
  }'
```

### List All Listings (Admin)
```bash
curl http://localhost:8000/api/admin/listings
```

### List Active Listings (Public)
```bash
curl http://localhost:8000/api/listings
```

### Filter Active Listings
```bash
curl "http://localhost:8000/api/listings?category_id=cat-123&location=Riyadh&skip=0&limit=20"
```

### Get Single Listing
```bash
curl http://localhost:8000/api/listings/listing-123
```

### Get User's Listings
```bash
curl http://localhost:8000/api/user/listings/user/user-456
```

### Update Listing
```bash
curl -X PUT http://localhost:8000/api/admin/listings/listing-123 \
  -H "Content-Type: application/json" \
  -d '{
    "price": 799.99,
    "location": "Jeddah"
  }'
```

### Delete Listing
```bash
curl -X DELETE http://localhost:8000/api/admin/listings/listing-123
```

### List All Users
```bash
curl http://localhost:8000/api/admin/users
```

### Get Single User
```bash
curl http://localhost:8000/api/admin/users/user-456
```

---

## Python Examples

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# ===== CREATE LISTING =====
def create_listing():
    response = requests.post(
        f"{BASE_URL}/api/admin/listings",
        json={
            "title": "iPhone 14",
            "description": "Like new",
            "category_id": "cat-123",
            "user_id": "user-456",
            "price": 899.99,
            "location": "Riyadh"
        }
    )
    return response.json()

# ===== LIST LISTINGS =====
def list_listings(skip=0, limit=20):
    response = requests.get(
        f"{BASE_URL}/api/listings",
        params={"skip": skip, "limit": limit}
    )
    return response.json()

# ===== FILTER LISTINGS =====
def filter_listings(category_id, location, skip=0, limit=20):
    response = requests.get(
        f"{BASE_URL}/api/listings",
        params={
            "category_id": category_id,
            "location": location,
            "skip": skip,
            "limit": limit
        }
    )
    return response.json()

# ===== GET LISTING =====
def get_listing(listing_id):
    response = requests.get(f"{BASE_URL}/api/listings/{listing_id}")
    return response.json()

# ===== UPDATE LISTING =====
def update_listing(listing_id, updates):
    response = requests.put(
        f"{BASE_URL}/api/admin/listings/{listing_id}",
        json=updates
    )
    return response.json()

# ===== DELETE LISTING =====
def delete_listing(listing_id):
    response = requests.delete(f"{BASE_URL}/api/admin/listings/{listing_id}")
    return response.json()

# ===== GET USER LISTINGS =====
def get_user_listings(user_id, skip=0, limit=20):
    response = requests.get(
        f"{BASE_URL}/api/user/listings/user/{user_id}",
        params={"skip": skip, "limit": limit}
    )
    return response.json()

# ===== LIST USERS =====
def list_users(skip=0, limit=100):
    response = requests.get(
        f"{BASE_URL}/api/admin/users",
        params={"skip": skip, "limit": limit}
    )
    return response.json()

# ===== GET USER =====
def get_user(user_id):
    response = requests.get(f"{BASE_URL}/api/admin/users/{user_id}")
    return response.json()

# Usage examples
if __name__ == "__main__":
    # Create listing
    listing = create_listing()
    print(f"Created listing: {listing['id']}")
    
    # List listings
    listings = list_listings(limit=20)
    print(f"Found {len(listings)} listings")
    
    # Filter listings
    filtered = filter_listings("cat-123", "Riyadh")
    print(f"Found {len(filtered)} filtered listings")
    
    # Get single listing
    single = get_listing(listing['id'])
    print(f"Title: {single['title']}")
    
    # Update listing
    updated = update_listing(listing['id'], {"price": 799.99})
    print(f"New price: {updated['price']}")
    
    # Get user listings
    user_listings = get_user_listings("user-456")
    print(f"User has {len(user_listings)} listings")
    
    # List users
    users = list_users(limit=50)
    print(f"Found {len(users)} users")
    
    # Get single user
    user = get_user("user-456")
    print(f"User: {user['name']}")
    
    # Delete listing
    result = delete_listing(listing['id'])
    print(result['message'])
```

---

## Access Control Matrix

| Operation | Admin | Public | User |
|-----------|-------|--------|------|
| Create Listing | ✓ | ✗ | ✓ |
| List All Listings | ✓ | ✗ | ✗ |
| List Active Listings | ✗ | ✓ | ✗ |
| List Own Listings | ✗ | ✗ | ✓ |
| Get Any Listing | ✓ | ✓ (active) | ✓ (own/active) |
| Update Any Listing | ✓ | ✗ | ✓ (own only) |
| Delete Any Listing | ✓ | ✗ | ✓ (own only) |
| List Users | ✓ | ✗ | ✗ |
| Get User | ✓ | ✗ | ✗ |

---

## Rate Limiting & Pagination

**No rate limiting** is currently implemented. Consider adding:
- Per-IP rate limiting (e.g., 100 requests/minute)
- Per-user rate limiting (after auth is added)

**Pagination best practices:**
- Always use pagination to limit data transfer
- Maximum 500 items per request
- Use skip/limit for offset-based pagination
- Example: `GET /api/listings?skip=0&limit=100`

---

## Performance Tips

1. **Pagination**: Always use skip/limit parameters
2. **Filtering**: Use category_id and location filters
3. **Indexing**: Database has indexes on:
   - user_id
   - category_id
   - is_active
   - location
4. **Caching**: Consider caching frequently accessed:
   - Active listings
   - Categories
   - Popular locations

---

## Documentation Links

- Full Setup Guide: [CRUD_SETUP_GUIDE.md](./CRUD_SETUP_GUIDE.md)
- Quick Reference: [API_QUICK_REFERENCE.md](./API_QUICK_REFERENCE.md)
- Architecture: [ARCHITECTURE.md](./ARCHITECTURE.md)
- Detailed Docs: [docs/CRUD_OPERATIONS.md](./docs/CRUD_OPERATIONS.md)

---

**Last Updated**: December 30, 2024
**API Version**: 1.0.0
**Status**: ✅ Complete and Tested
