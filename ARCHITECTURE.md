# Architecture & API Flow Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                      │
│                        (main.py)                                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        ┌───────▼────────┐   ┌──▼──────────┐   ┌─▼──────────┐
        │ Health Routes  │   │   Admin     │   │ Categories │
        │ (health.py)    │   │  (admin.py) │   │(categ..py) │
        └────────────────┘   └──┬─────────┬┘   └─┬──────────┘
                                │         │      │
                        ┌───────▴─────────▴──────┴────────┐
                        │                                 │
                    ┌───▼──────────────────────────────┐ │
                    │   NEW: Listings Routes           │ │
                    │   (listings.py)                  │ │
                    │                                  │ │
                    │  Admin: Full CRUD                │ │
                    │  Public: Read-only (active)      │ │
                    │  User: Own listings only         │ │
                    └──────────────────────────────────┘ │
                                                         │
                        ┌────────────────────────────────┘
                        │
                    ┌───▼──────────────────────┐
                    │  Pydantic Schemas        │
                    │  (models/schemas.py)     │
                    │                          │
                    │  • UserCreate/Out        │
                    │  • CategoryCreate/Out    │
                    │  • NEW: ListingCreate    │
                    │  • NEW: ListingUpdate    │
                    │  • NEW: ListingOut       │
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │  Supabase Database        │
                    │  (supabase_client.py)     │
                    │                           │
                    │  • users table            │
                    │  • categories table       │
                    │  • NEW: listings table    │
                    └───────────────────────────┘
```

## API Endpoint Hierarchy

```
/api/
├── health/                          (existing)
│   └── GET /

├── admin/                           (existing)
│   ├── POST /signup
│   ├── POST /login
│   ├── POST /change-password
│   ├── GET /users                   (NEW)
│   └── GET /users/{user_id}         (NEW)
│
├── admin/categories/                (existing)
│   ├── POST /
│   ├── GET /
│   ├── GET /{id}
│   ├── PUT /{id}
│   └── DELETE /{id}
│
├── categories/active                (existing)
│   └── GET /
│
├── admin/listings/                  (NEW)
│   ├── POST /                       Create
│   ├── GET /                        List all
│   ├── GET /{id}                    Get one
│   ├── PUT /{id}                    Update
│   └── DELETE /{id}                 Delete
│
├── listings/                        (NEW - PUBLIC)
│   ├── GET /                        List active
│   └── GET /{id}                    Get active
│
└── user/listings/                   (NEW - USER)
    ├── POST /                       Create
    ├── GET /user/{user_id}          Get user's
    ├── PUT /{id}                    Update
    └── DELETE /{id}                 Delete
```

## Data Model Relationships

```
┌──────────────────┐
│     USERS        │
├──────────────────┤
│ id (PK)          │
│ name             │
│ email (UNIQUE)   │
│ password_hash    │
│ created_at       │
│ updated_at       │
└────────┬─────────┘
         │ (1:N)
         │
         ├──────────────────────┐
         │                      │
         │              ┌───────▼─────────────┐
         │              │    LISTINGS (NEW)   │
         │              ├─────────────────────┤
         │              │ id (PK)             │
         │              │ title               │
         │              │ description         │
         │              │ price               │
         │              │ location            │
         │              │ phone_number        │
         │              │ image_url           │
         │              │ is_active           │
         │              │ user_id (FK)◄───────┤
         │              │ category_id (FK)───┐│
         │              │ created_at          ││
         │              │ updated_at          ││
         │              └─────────────────────┘│
         │                                     │
         └─────────────────────────────────────┘
                         │
                    (1:N)│
                         │
            ┌────────────▼───────────┐
            │    CATEGORIES          │
            ├───────────────────────┐
            │ id (PK)               │
            │ name (UNIQUE)         │
            │ is_active             │
            │ created_at            │
            │ updated_at            │
            └───────────────────────┘
```

## Request-Response Flow

### Create Listing Flow
```
Client
  │
  ├─ POST /api/admin/listings
  │   └─ JSON: {title, description, category_id, user_id, price, location}
  │
  ▼
FastAPI Router (listings.py)
  │
  ├─ Validate input (Pydantic schema)
  │
  ├─ Check category exists
  │   └─ Query categories table
  │
  ├─ Check user exists
  │   └─ Query users table
  │
  ├─ Insert into listings table
  │   └─ Supabase client
  │
  ▼
Return 200 OK + Listing object
  │
  └─ Include id, created_at, updated_at
```

### List Listings Flow
```
Client
  │
  ├─ GET /api/listings?category_id=xxx&location=Riyadh&skip=0&limit=20
  │
  ▼
FastAPI Router (listings.py)
  │
  ├─ Validate query parameters
  │
  ├─ Build query:
  │   ├─ WHERE is_active = true
  │   ├─ AND category_id = xxx (if provided)
  │   ├─ AND location = Riyadh (if provided)
  │   ├─ LIMIT 20
  │   └─ OFFSET 0
  │
  ├─ Execute query via Supabase
  │
  ▼
Return 200 OK + [Listings array]
```

### Update Listing Flow
```
Client
  │
  ├─ PUT /api/admin/listings/{id}
  │   └─ JSON: {price: 799.99}  (partial update)
  │
  ▼
FastAPI Router (listings.py)
  │
  ├─ Validate input
  │
  ├─ Check listing exists
  │   └─ Query by id
  │
  ├─ Build update data (only provided fields)
  │
  ├─ Validate foreign keys (if category changed)
  │
  ├─ Update in database
  │
  ▼
Return 200 OK + Updated Listing object
```

### Delete Listing Flow
```
Client
  │
  ├─ DELETE /api/admin/listings/{id}
  │
  ▼
FastAPI Router (listings.py)
  │
  ├─ Check listing exists
  │
  ├─ Delete from database
  │
  ▼
Return 200 OK + {message, id}
```

## Authentication Levels

```
╔════════════════════════════════════════════════════════╗
║                    ENDPOINTS MATRIX                    ║
╠════════════════════════════════════════════════════════╣
║  Access Level  │  Create  │  Read   │  Update  │  Delete
╠════════════════════════════════════════════════════════╣
║  Admin         │   ✓      │   ✓✓    │    ✓✓    │   ✓✓
║  Public        │   ✗      │   ✓     │    ✗     │   ✗
║  User          │   ✓      │   ✓     │    ✓     │   ✓
║  (own only)    │  (own)   │(own/all)│ (own)    │ (own)
╚════════════════════════════════════════════════════════╝

Legend:
✓  = Access granted
✓✓ = Full access (all records)
✓  = Limited access (own records)
✗  = No access
```

## Pagination Visualization

```
Database: 250 total listings

Page 1 (skip=0, limit=20):
  [1] [2] [3] ... [20] | [21] [22] ... [100]
   ▲
   └─ You are here

Page 2 (skip=20, limit=20):
  [1] [2] ... [20] | [21] [22] [23] ... [40] | [41] ...
                    ▲
                    └─ You are here

Page 3 (skip=40, limit=20):
  [1] ... [40] | [41] [42] [43] ... [60] | [61] ...
               ▲
               └─ You are here

Total pages = ceil(250 / 20) = 13 pages
```

## Database Query Examples

### Create Listing
```sql
INSERT INTO listings (
  title, description, category_id, user_id, price,
  location, phone_number, image_url, is_active,
  created_at, updated_at
) VALUES (
  'iPhone 14', 'Excellent', 'cat-123', 'user-456', 899.99,
  'Riyadh', '+966501234567', 'https://...', true,
  NOW(), NOW()
)
RETURNING *;
```

### List Active Listings with Filters
```sql
SELECT * FROM listings
WHERE is_active = true
  AND category_id = 'cat-123'
  AND location = 'Riyadh'
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;
```

### Update Listing
```sql
UPDATE listings
SET price = 799.99, updated_at = NOW()
WHERE id = 'listing-123'
RETURNING *;
```

### Delete Listing
```sql
DELETE FROM listings
WHERE id = 'listing-123'
RETURNING id;
```

### List All Users
```sql
SELECT id, name, email FROM users
ORDER BY created_at DESC
LIMIT 100 OFFSET 0;
```

## HTTP Status Code Flow

```
Success Path:
  Client Request
      │
      ├─ Valid input ─────────────────────┐
      │                                   │
      └─ Invalid input ─────────────────┐ │
                                        │ │
                        ┌───────────────┘ │
                        │                 │
              ┌─────────▼────────┐  ┌────▼──────────┐
              │  400 Bad Request │  │  200 OK       │
              └──────────────────┘  │  or           │
                                    │  201 Created  │
                                    └───────────────┘

Error Path:
  Database Error ─┐
  Record not found├──────────► 404 Not Found
  Auth failed ────┤
                  ├──────────► 401 Unauthorized
  Server error ───┤
                  └──────────► 500 Server Error
```

## Performance Considerations

```
Query Performance:

┌─ Direct Lookups (Fast)
│  ├─ By ID: O(1) - Primary key index
│  └─ By User ID: O(log n) - Foreign key index
│
├─ Filters (Medium)
│  ├─ By category: O(log n) - Indexed
│  ├─ By location: O(log n) - Indexed
│  └─ By is_active: O(log n) - Indexed
│
└─ Complex Queries (Slower)
   ├─ Multiple filters: O(log n) + O(log n)
   └─ Large result sets: Consider pagination

Optimization Tips:
  ✓ Always use pagination (max 500 items)
  ✓ Use filters to narrow results
  ✓ Database has indexes on common fields
  ✓ Don't fetch full text for lists
```

## Code Organization

```
backend/
│
├── main.py
│   └─ Initializes FastAPI
│      Registers all routers
│      CORS configuration
│
├── config/
│   └── settings.py
│       └─ Environment variables
│
├── models/
│   └── schemas.py
│       ├─ UserCreate, UserOut
│       ├─ CategoryCreate, CategoryOut
│       └─ ListingCreate, ListingUpdate, ListingOut
│
├── routes/
│   ├── health.py (existing)
│   ├── admin.py (updated)
│   │   ├─ Sign up, login, change password
│   │   └─ List/get users (NEW)
│   ├── categories.py (existing)
│   │   ├─ Admin routes
│   │   └─ Public routes
│   └── listings.py (NEW)
│       ├─ Admin routes (full CRUD)
│       ├─ Public routes (read-only)
│       └─ User routes (own content)
│
└── db/
    └── supabase_client.py
        ├─ insert()
        ├─ select()
        ├─ select_one()
        ├─ update()
        └─ delete()
```

This architecture provides:
- **Separation of concerns** - Routes, models, database logic
- **Scalability** - Easy to add new routes and endpoints
- **Maintainability** - Clear code structure
- **Security** - Multiple access levels
- **Performance** - Indexed database queries with pagination
