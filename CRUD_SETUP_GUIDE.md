# CRUD Operations Guide - Complete Setup

## What Was Implemented

A complete CRUD (Create, Read, Update, Delete) system for managing listings and users with three different access levels: Admin, Public, and User.

### Listings Management (11 Endpoints)

#### Admin Level (Full Control)
- Create listings
- View all listings
- Get specific listing
- Update any listing
- Delete any listing

#### Public Level (Read-Only)
- View active listings only
- Search by category and location
- Get specific active listing

#### User Level (Own Content)
- Create own listings
- View own listings
- Update own listings
- Delete own listings

### User Management (2 Endpoints)
- List all users (admin)
- Get specific user details (admin)

---

## Project Structure

```
backend/
├── models/
│   └── schemas.py           (Updated - Added Listing schemas)
├── routes/
│   ├── admin.py             (Updated - Added user endpoints)
│   ├── categories.py        (Existing)
│   ├── health.py            (Existing)
│   └── listings.py          (NEW - All listing CRUD)
├── db/
│   └── supabase_client.py   (Existing - Database client)
├── config/
│   └── settings.py          (Existing)
└── main.py                  (Updated - Registered routes)
```

---

## Installation & Setup

### 1. Verify Dependencies
Ensure your `requirements.txt` includes:
```
fastapi==0.104.1
uvicorn==0.24.0
supabase==2.3.4
pydantic==2.5.0
pydantic[email]==2.5.0
passlib==1.7.4
bcrypt==4.1.1
python-dotenv==1.0.0
```

### 2. Database Setup
Create the `listings` table in Supabase:

```sql
-- Create listings table
CREATE TABLE listings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  price DECIMAL(10, 2) NOT NULL,
  location TEXT NOT NULL,
  phone_number TEXT,
  image_url TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_listings_user_id ON listings(user_id);
CREATE INDEX idx_listings_category_id ON listings(category_id);
CREATE INDEX idx_listings_is_active ON listings(is_active);
CREATE INDEX idx_listings_location ON listings(location);
```

### 3. Environment Setup
Ensure `.env` file has:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
API_PORT=8000
DEBUG=True
```

### 4. Run the Server
```bash
cd backend
python main.py
```

The API will be available at: `http://localhost:8000`

---

## Complete API Reference

### 1. Create Listing

**Endpoint:** `POST /api/admin/listings` or `POST /api/user/listings`

**Request:**
```json
{
  "title": "iPhone 14 Pro Max",
  "description": "Brand new, sealed box",
  "category_id": "12345678-1234-1234-1234-123456789012",
  "user_id": "87654321-4321-4321-4321-210987654321",
  "price": 1299.99,
  "location": "Riyadh",
  "phone_number": "+966501234567",
  "image_url": "https://example.com/iphone.jpg",
  "is_active": true
}
```

**Response:** 200 OK
```json
{
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "title": "iPhone 14 Pro Max",
  "description": "Brand new, sealed box",
  "category_id": "12345678-1234-1234-1234-123456789012",
  "user_id": "87654321-4321-4321-4321-210987654321",
  "price": 1299.99,
  "location": "Riyadh",
  "phone_number": "+966501234567",
  "image_url": "https://example.com/iphone.jpg",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Errors:**
- `400`: Missing required fields or invalid data
- `404`: Category or User not found

---

### 2. List Listings

**Admin (All Listings):**
```
GET /api/admin/listings?skip=0&limit=20
```

**Public (Active Only):**
```
GET /api/listings?skip=0&limit=20&category_id=xxx&location=Riyadh
```

**User (Own Listings):**
```
GET /api/user/listings/user/{user_id}?skip=0&limit=20
```

**Response:** 200 OK
```json
[
  {
    "id": "listing-1",
    "title": "iPhone 14 Pro Max",
    "description": "Brand new, sealed box",
    "category_id": "cat-1",
    "user_id": "user-1",
    "price": 1299.99,
    "location": "Riyadh",
    "phone_number": "+966501234567",
    "image_url": "https://example.com/iphone.jpg",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Max records to return (default: 100, max: 500)
- `category_id`: Filter by category (public only)
- `location`: Filter by location (public only)

---

### 3. Get Single Listing

**Admin:**
```
GET /api/admin/listings/{listing_id}
```

**Public (Active Only):**
```
GET /api/listings/{listing_id}
```

**Response:** 200 OK (single listing object)

**Errors:**
- `404`: Listing not found

---

### 4. Update Listing

**Endpoint:** `PUT /api/admin/listings/{listing_id}` or `PUT /api/user/listings/{listing_id}`

**Request (All Fields Optional):**
```json
{
  "title": "Updated Title",
  "price": 999.99,
  "is_active": false
}
```

**Response:** 200 OK (updated listing object)

**Errors:**
- `404`: Listing not found
- `400`: Invalid category if changed

---

### 5. Delete Listing

**Endpoint:** `DELETE /api/admin/listings/{listing_id}` or `DELETE /api/user/listings/{listing_id}`

**Response:** 200 OK
```json
{
  "message": "Listing deleted successfully",
  "id": "listing-id"
}
```

**Errors:**
- `404`: Listing not found

---

### 6. List Users

**Endpoint:** `GET /api/admin/users?skip=0&limit=100`

**Response:** 200 OK
```json
[
  {
    "id": "user-1",
    "name": "John Doe",
    "email": "john@example.com"
  },
  {
    "id": "user-2",
    "name": "Jane Smith",
    "email": "jane@example.com"
  }
]
```

---

### 7. Get Single User

**Endpoint:** `GET /api/admin/users/{user_id}`

**Response:** 200 OK
```json
{
  "id": "user-1",
  "name": "John Doe",
  "email": "john@example.com"
}
```

**Errors:**
- `404`: User not found

---

## Example Usage

### Using curl

**Create a listing:**
```bash
curl -X POST http://localhost:8000/api/admin/listings \
  -H "Content-Type: application/json" \
  -d '{
    "title": "iPhone 14",
    "description": "Excellent condition",
    "category_id": "cat-123",
    "user_id": "user-456",
    "price": 899.99,
    "location": "Riyadh"
  }'
```

**List listings:**
```bash
curl http://localhost:8000/api/listings
```

**Filter listings:**
```bash
curl "http://localhost:8000/api/listings?category_id=cat-123&location=Riyadh&skip=0&limit=10"
```

**Update listing:**
```bash
curl -X PUT http://localhost:8000/api/admin/listings/listing-123 \
  -H "Content-Type: application/json" \
  -d '{"price": 799.99}'
```

**Delete listing:**
```bash
curl -X DELETE http://localhost:8000/api/admin/listings/listing-123
```

**List users:**
```bash
curl http://localhost:8000/api/admin/users
```

### Using Python requests

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Create listing
data = {
    "title": "iPhone 14",
    "description": "Excellent condition",
    "category_id": "cat-123",
    "user_id": "user-456",
    "price": 899.99,
    "location": "Riyadh"
}
response = requests.post(f"{BASE_URL}/api/admin/listings", json=data)
listing = response.json()
print(f"Created listing: {listing['id']}")

# List listings
response = requests.get(f"{BASE_URL}/api/listings")
listings = response.json()
print(f"Found {len(listings)} active listings")

# Update listing
update_data = {"price": 799.99}
response = requests.put(
    f"{BASE_URL}/api/admin/listings/{listing['id']}",
    json=update_data
)
updated = response.json()
print(f"Updated price to: {updated['price']}")

# Delete listing
response = requests.delete(f"{BASE_URL}/api/admin/listings/{listing['id']}")
print(response.json())

# List users
response = requests.get(f"{BASE_URL}/api/admin/users")
users = response.json()
print(f"Found {len(users)} users")
```

---

## Pagination Examples

**Get first 20 listings:**
```bash
GET /api/listings?skip=0&limit=20
```

**Get next 20 listings (page 2):**
```bash
GET /api/listings?skip=20&limit=20
```

**Get next 20 listings (page 3):**
```bash
GET /api/listings?skip=40&limit=20
```

**Maximum page size (500 items):**
```bash
GET /api/listings?skip=0&limit=500
```

---

## Filter Examples

**Filter by category:**
```bash
GET /api/listings?category_id=12345678-1234-1234-1234-123456789012
```

**Filter by location:**
```bash
GET /api/listings?location=Riyadh
```

**Filter by both:**
```bash
GET /api/listings?category_id=12345678-1234-1234-1234-123456789012&location=Riyadh
```

**With pagination:**
```bash
GET /api/listings?category_id=xxx&location=Riyadh&skip=0&limit=20
```

---

## HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Operation completed successfully |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid input or missing fields |
| 401 | Unauthorized | Authentication failed |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Database or server error |

---

## Error Response Format

All errors follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Swagger Documentation

Access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Key Features

✅ **Full CRUD Operations** - Create, Read, Update, Delete listings  
✅ **Multiple Access Levels** - Admin, Public, User  
✅ **Advanced Filtering** - By category and location  
✅ **Pagination** - Skip/limit pagination  
✅ **Validation** - Foreign key and field validation  
✅ **Status Management** - Active/inactive listings  
✅ **Timestamps** - Created and updated tracking  
✅ **Error Handling** - Comprehensive error messages  
✅ **Documentation** - Full API documentation  

---

## Troubleshooting

### Database Connection Error
**Error:** `ValueError: Supabase URL and Key must be set`  
**Solution:** Check `.env` file has `SUPABASE_URL` and `SUPABASE_KEY`

### Table Not Found
**Error:** `404 Not Found for table: listings`  
**Solution:** Create the listings table in Supabase using the SQL provided above

### CORS Error
**Fix:** CORS is already enabled for all origins in `main.py`

### Invalid UUID
**Error:** `400 Bad Request`  
**Solution:** Ensure category_id and user_id are valid UUIDs from your database

---

## Performance Tips

1. **Use pagination** - Don't fetch thousands of records at once
2. **Use filters** - Narrow results with category_id and location
3. **Check database indexes** - Listings table has indexes on common filters
4. **Limit page size** - Maximum 500 items per request is good for performance

---

## Next Steps

1. **Test the API** - Use Swagger UI at http://localhost:8000/docs
2. **Connect Frontend** - Use the API endpoints in your mobile/web app
3. **Add Authentication** - Implement JWT tokens for security
4. **Add Search** - Implement full-text search in listings
5. **Add Sorting** - Sort listings by price, date, etc.
6. **Add Images** - Implement image upload functionality

---

## Support Files

- [API_QUICK_REFERENCE.md](../API_QUICK_REFERENCE.md) - Quick endpoint reference
- [IMPLEMENTATION_CHECKLIST.md](../IMPLEMENTATION_CHECKLIST.md) - What was implemented
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - Detailed summary
- [docs/CRUD_OPERATIONS.md](../docs/CRUD_OPERATIONS.md) - Complete documentation

