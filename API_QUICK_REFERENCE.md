# Quick API Reference

## Base URL
```
http://localhost:8000
```

## Authentication
Currently no authentication middleware. Add JWT/Bearer token validation as needed.

---

## Listings - Create
```bash
POST /api/admin/listings
POST /api/user/listings

Body:
{
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "user_id": "uuid",
  "price": 99.99,
  "location": "string",
  "phone_number": "string (optional)",
  "image_url": "string (optional)",
  "is_active": true (optional)
}

Success: 200 OK
```

---

## Listings - Read
```bash
GET /api/admin/listings                    # All listings
GET /api/listings                          # Active only
GET /api/listings?category_id=xxx&location=Riyadh  # With filters
GET /api/admin/listings/{id}              # Single listing
GET /api/listings/{id}                    # Single active
GET /api/user/listings/user/{user_id}     # User's listings

Query params:
- skip: int (default: 0)
- limit: int (default: 100, max: 500)
- category_id: uuid (optional)
- location: string (optional)

Success: 200 OK, returns array or object
```

---

## Listings - Update
```bash
PUT /api/admin/listings/{id}
PUT /api/user/listings/{id}

Body (all optional):
{
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "price": 99.99,
  "location": "string",
  "phone_number": "string",
  "image_url": "string",
  "is_active": true
}

Success: 200 OK
```

---

## Listings - Delete
```bash
DELETE /api/admin/listings/{id}
DELETE /api/user/listings/{id}

Success: 200 OK
Response: {"message": "Listing deleted successfully", "id": "xxx"}
```

---

## Users - List/Get
```bash
GET /api/admin/users                  # All users
GET /api/admin/users/{id}             # Single user

Query params:
- skip: int (default: 0)
- limit: int (default: 100, max: 500)

Success: 200 OK
Returns: {id, name, email} (no passwords!)
```

---

## Users - Authentication
```bash
POST /api/admin/signup
Body: {name, email, password}

POST /api/admin/login
Body: {email, password}

POST /api/admin/change-password
Body: {email, new_password}
```

---

## Categories (Existing)
```bash
# Admin
POST /api/admin/categories
GET /api/admin/categories
GET /api/admin/categories/{id}
PUT /api/admin/categories/{id}
DELETE /api/admin/categories/{id}

# Public
GET /api/categories/active
```

---

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Auth failed |
| 404 | Not Found - Resource missing |
| 500 | Server Error |

---

## Error Format
```json
{
  "detail": "Error message here"
}
```

---

## Common Errors

### 404 Not Found
- Listing doesn't exist
- User doesn't exist
- Category doesn't exist

### 400 Bad Request
- Missing required fields
- Invalid data type
- Category/User reference doesn't exist

### 500 Server Error
- Database connection issues
- Supabase errors

---

## Examples

### Create & List Listings
```bash
# Create
curl -X POST http://localhost:8000/api/admin/listings \
  -H "Content-Type: application/json" \
  -d '{
    "title": "iPhone 14",
    "description": "Used, excellent",
    "category_id": "abc123",
    "user_id": "def456",
    "price": 899.99,
    "location": "Riyadh"
  }'

# List all
curl http://localhost:8000/api/listings

# Filter by category and location
curl "http://localhost:8000/api/listings?category_id=abc123&location=Riyadh"

# Get user listings
curl http://localhost:8000/api/user/listings/user/def456

# Update price
curl -X PUT http://localhost:8000/api/admin/listings/listing123 \
  -H "Content-Type: application/json" \
  -d '{"price": 799.99}'

# Delete
curl -X DELETE http://localhost:8000/api/admin/listings/listing123
```

---

## Database Tables Required

### listings
- id, title, description, category_id, user_id
- price, location, phone_number, image_url
- is_active, created_at, updated_at

### users
- id, name, email, password_hash
- created_at, updated_at

### categories
- id, name, is_active
- created_at, updated_at

---

## Pagination Example
```bash
# First 20
curl "http://localhost:8000/api/listings?skip=0&limit=20"

# Next 20
curl "http://localhost:8000/api/listings?skip=20&limit=20"

# Large page (max 500)
curl "http://localhost:8000/api/listings?skip=0&limit=500"
```

---

## API Documentation
- Full docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
