# Supabase Setup & Migration Guide
## Coming from Django + AWS S3

### 1. Initial Setup

#### Get your Supabase credentials
1. Go to [supabase.com](https://supabase.com)
2. Create a new project
3. Go to **Settings → API**
4. Copy:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_KEY`

#### Create `.env` file
```env
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
OTP_API_KEY=your_twilio_or_sendgrid_key
JWT_SECRET=your_secret_key_here
```

---

### 2. Database Schema Setup

In Supabase dashboard, go to **SQL Editor** and run these queries:

#### Users Table
```sql
create table users (
  id uuid default gen_random_uuid() primary key,
  email varchar(255) unique not null,
  name varchar(255) not null,
  phone varchar(20),
  password_hash varchar(255),
  created_at timestamp default now(),
  updated_at timestamp default now()
);

create index users_email_idx on users(email);
```

#### OTP Table
```sql
create table otps (
  id uuid default gen_random_uuid() primary key,
  email varchar(255),
  phone varchar(20),
  otp_code varchar(6),
  expires_at timestamp,
  created_at timestamp default now()
);

create index otps_email_idx on otps(email);
create index otps_phone_idx on otps(phone);
```

#### Conversations Table
```sql
create table conversations (
  id uuid default gen_random_uuid() primary key,
  user1_id uuid not null references users(id) on delete cascade,
  user2_id uuid not null references users(id) on delete cascade,
  created_at timestamp default now(),
  last_message_at timestamp
);

create index conversations_users_idx on conversations(user1_id, user2_id);
```

#### Messages Table
```sql
create table messages (
  id uuid default gen_random_uuid() primary key,
  conversation_id uuid not null references conversations(id) on delete cascade,
  sender_id uuid not null references users(id) on delete cascade,
  content text not null,
  created_at timestamp default now(),
  updated_at timestamp
);

create index messages_conversation_idx on messages(conversation_id);
create index messages_sender_idx on messages(sender_id);
```

---

### 3. Django to Supabase Comparison

| Django | Supabase | Notes |
|--------|----------|-------|
| `Model.objects.create()` | `db.insert(table, data)` | Both create new records |
| `Model.objects.get(id=id)` | `db.select_one(table, id)` | Get single record |
| `Model.objects.all()` | `db.select(table)` | Get all records |
| `Model.objects.filter(field=value)` | `db.select(table, filters={"field": value})` | Filter records |
| `Model.objects.filter().update()` | `db.update(table, id, data)` | Update records |
| `Model.objects.filter().delete()` | `db.delete(table, id)` | Delete records |
| Django ORM Queryset | `db.query(table, custom_func)` | Complex queries |

---

### 4. Usage Examples

#### Example 1: Create a User
```python
from db.supabase_client import db

# Create user
user = db.insert("users", {
    "email": "john@example.com",
    "name": "John Doe",
    "phone": "+1234567890",
    "password_hash": "hashed_password"
})

print(user)  # Returns: {"id": "uuid", "email": "john@example.com", ...}
```

#### Example 2: Get User by Email
```python
# Get single user by email
users = db.select("users", filters={"email": "john@example.com"})
user = users[0] if users else None
```

#### Example 3: Update User
```python
# Update user
updated = db.update("users", user_id, {
    "name": "Jane Doe",
    "phone": "+9876543210"
})
```

#### Example 4: Complex Query - Get User's Conversations
```python
from db.supabase_client import db

client = db.get_client()

# Get all conversations for a user
response = client.table("conversations").select("*").or_(
    f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
).execute()

conversations = response.data
```

#### Example 5: Paginated Messages
```python
client = db.get_client()

# Get messages with pagination
limit = 50
offset = 0

response = client.table("messages").select("*").eq(
    "conversation_id", conversation_id
).order("created_at", desc=False).range(offset, offset + limit - 1).execute()

messages = response.data
```

---

### 5. Key Differences from Django

#### 1. **No ORM**
- Django: `User.objects.filter(age__gt=18).count()`
- Supabase: Use raw SQL or client library filters

#### 2. **Async Friendly**
- FastAPI is async, Supabase client works with async/await
- Django is synchronous by default

#### 3. **Auto-generated IDs**
- Django: `id` field is auto-generated (integer)
- Supabase: Uses `uuid` by default (better for distributed systems)

#### 4. **No Migrations File**
- Django: `python manage.py makemigrations` + `python manage.py migrate`
- Supabase: Write SQL directly in dashboard (no migration files needed)

#### 5. **Real-time Support**
- Django: Need to use WebSockets separately
- Supabase: Built-in real-time subscriptions (perfect for chat!)

---

### 6. Enable Real-time for Chat (Optional)

In Supabase dashboard:
1. Go to **Database → Replication**
2. Enable replication for `messages` and `conversations` tables

Then use:
```python
from db.supabase_client import db

client = db.get_client()

# Subscribe to new messages in a conversation
response = client.realtime.on('*', {
    'event': 'INSERT',
    'schema': 'public',
    'table': 'messages'
}, lambda payload: print(f"New message: {payload}")).subscribe()
```

---

### 7. File Storage (S3 Equivalent)

Supabase Storage is like S3:
```python
# Upload file
client = db.get_client()

with open("file.jpg", "rb") as f:
    response = client.storage.from_("chat_files").upload(
        f"conversations/{conversation_id}/file.jpg",
        f
    )

# Get public URL
url = client.storage.from_("chat_files").get_public_url(
    f"conversations/{conversation_id}/file.jpg"
)
```

---

### 8. Authentication vs OTP

- **Supabase Auth**: Built-in email/password, OAuth, magic links
- **Your OTP Flow**: 
  1. User requests OTP → Send via Twilio/SendGrid
  2. Store OTP code + expiry in `otps` table
  3. User verifies OTP → Check against `otps` table
  4. Create JWT token for authentication

---

### 9. Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python backend/main.py

# Server will be at http://localhost:8000
# API docs at http://localhost:8000/docs
```

---

### 10. Testing Endpoints

```bash
# Create user
curl -X POST http://localhost:8000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User",
    "phone": "+1234567890",
    "password": "securepass123"
  }'

# Create conversation
curl -X POST http://localhost:8000/api/chat/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "user1_id": "uuid1",
    "user2_id": "uuid2"
  }'

# Send message
curl -X POST http://localhost:8000/api/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-uuid",
    "sender_id": "user-uuid",
    "content": "Hello!"
  }'
```

---

### 11. Troubleshooting

**Problem**: `"Supabase URL and Key must be set"`
- **Solution**: Make sure `.env` file exists and has `SUPABASE_URL` and `SUPABASE_KEY`

**Problem**: `{"code":"401","message":"Unauthorized"}`
- **Solution**: Check your SUPABASE_KEY is correct (should be `anon public`, not service role key)

**Problem**: `Table "users" not found`
- **Solution**: Create tables using SQL queries above in Supabase SQL Editor

---

### 12. Next Steps

1. ✅ Set up Supabase project
2. ✅ Create `.env` file with credentials
3. ✅ Run SQL queries to create tables
4. ✅ Test endpoints with curl/Postman
5. 🔄 Integrate OTP service (Twilio/SendGrid)
6. 🔄 Add JWT authentication
7. 🔄 Deploy to Render
8. 🔄 Connect from mobile/web frontend

---

**Questions?** Check [Supabase Docs](https://supabase.com/docs) or reply!
