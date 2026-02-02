# Project Summary

## Modules Present

The project is now streamlined to focus on **Admin Authentication** and **Category Management**.

### Core Modules
- **`main.py`**: Entry point, registers Admin and Category routers.
- **`config/settings.py`**: Environment variables (includes JWT config).
- **`db/supabase_client.py`**: Database interactions.
- **`utils/auth.py`**: JWT token generation and validation.

### API Routes (`backend/routes/`)
- **`health.py`**: System health check.
- **`admin.py`**: Admin authentication (Signup, Login, Password Change).
- **`categories.py`**: Category management (Admin CRUD + User Read).

### Data Models (`backend/models/schemas.py`)
- **User**: `UserCreate`, `UserOut`, `LoginRequest`, `ChangePasswordRequest`.
- **Token**: `Token` (access_token, token_type).
- **Category**: `CategoryCreate`, `CategoryUpdate`, `CategoryOut`.

---

## All APIs Present

### 1. Category Management (Admin - **PROTECTED**)
*Requires `Authorization: Bearer <token>` header*

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/admin/categories/` | Create a new category |
| `GET` | `/api/admin/categories/` | List all categories (with pagination) |
| `GET` | `/api/admin/categories/{id}` | Get category details |
| `PUT` | `/api/admin/categories/{id}` | Update a category |
| `DELETE` | `/api/admin/categories/{id}` | Delete a category |

### 2. Category Browsing (User/Public)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/categories/` | List active categories (Root if no parent_id) |
| `GET` | `/api/categories/?parent_id={id}` | List sub-categories of a parent |
| `GET` | `/api/categories/{id}/is-leaf` | Check if category is a leaf node |

### 3. Admin Authentication
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/admin/signup` | Register new admin |
| `POST` | `/api/admin/login` | Admin login (Returns JWT) |
| `POST` | `/api/admin/change-password` | Change password (**PROTECTED**) |

### 4. Customer Authentication (OTP)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/send-otp` | Send OTP to phone (Creates/Updates User) |
| `POST` | `/api/auth/verify-otp` | Verify OTP (Returns JWT + User Info) |
| `POST` | `/api/auth/create-user` | Complete Profile/Set Name (**PROTECTED**) |

### 5. System
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check |

---

## Test Payloads and References

### Auth Payloads

#### Admin Login
**Endpoint:** `POST /api/admin/login`
```json
{
  "email": "admin@example.com",
  "password": "securepassword123"
}
```

#### Token Response
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Admin Signup
**Endpoint:** `POST /api/admin/signup`
```json
{
  "name": "New Admin",
  "email": "newadmin@example.com",
  "password": "strongpassword"
}
```

#### Change Password (Protected)
*Headers required:* `Authorization: Bearer <your_access_token>`
**Endpoint:** `POST /api/admin/change-password`
```json
{
  "email": "admin@example.com",
  "new_password": "newsecurepassword"
}
```

### Category Payloads (Admin)
*Headers required:* `Authorization: Bearer <your_access_token>`

#### Create Category (Root)
**Endpoint:** `POST /api/admin/categories/`
```json
{
  "name": "Vehicles",
  "image_url": "https://example.com/car.png",
  "is_active": true
}
```

#### Create Sub-Category with Attributes
**Endpoint:** `POST /api/admin/categories/`
```json
{
  "name": "Toyota",
  "parent_id": "uuid-of-vehicles-category",
  "image_url": "https://example.com/toyota.png",
  "attributes_schema": [
    {"name": "fuel_type", "type": "select", "options": ["Petrol", "Diesel"]},
    {"name": "year", "type": "number"}
  ]
}
```

#### Update Category
**Endpoint:** `PUT /api/admin/categories/{id}`
```json
{
  "name": "Home Appliances",
  "parent_id": "uuid-of-new-parent",
  "is_active": false
}
```

#### Category Response
```json
{
  "id": "...",
  "name_en": "Toyota",
  "name_ar": "تويوتا",
  "image_url": "https://example.com/toyota.png",
  "parent_id": "...",
  "attributes_schema": [...],
  "is_active": true
  ...
}
```

#### Check Leaf Node
**Endpoint:** `GET /api/categories/{id}/is-leaf`
**Response:**
```json
{
  "is_leaf": true,
  "id": "..."
}
```

### Customer Payloads (OTP)

#### Send OTP
**Endpoint:** `POST /api/auth/send-otp`
```json
{
  "phone_number": "+1234567890"
}
```
*Note: For MVP, hardcoded OTP is `123456`.*

#### Verify OTP
**Endpoint:** `POST /api/auth/verify-otp`
```json
{
  "phone_number": "+1234567890",
  "otp": "123456"
}
```
*Returns `access_token` and `user` object.*

#### Complete Profile (Create User)
*Headers required:* `Authorization: Bearer <access_token>`
**Endpoint:** `POST /api/auth/create-user`
```json
{
  "name": "John Doe"
}
```
*Updates the authenticated user's name.*
