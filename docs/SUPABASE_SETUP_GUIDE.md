# Supabase Setup Guide for 96sooq Backend

## Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Click **"Start your project"** or sign in if you have an account
3. Create a new organization (if needed)
4. Create a new project with:
   - **Project Name:** `96sooq`
   - **Database Password:** Create a strong password (save it!)
   - **Region:** Choose closest to your users
5. Wait 2-3 minutes for project to initialize

---

## Step 2: Get Your Supabase Credentials

1. Once your project is ready, go to **Settings → API**
2. Copy these two values:
   - **Project URL** → This is your `SUPABASE_URL`
   - **anon public** key → This is your `SUPABASE_KEY`

Example credentials look like:
```
SUPABASE_URL=https://abcdefghijklmnop.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Step 3: Update Your .env File

In `/workspaces/96sooq-backend/backend/.env`, replace the placeholder values:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key-here
API_PORT=8000
DEBUG=True
```

**Save the file!**

---

## Step 4: Create Database Tables

Go to your Supabase dashboard → **SQL Editor** → Click **"+ New Query"**

Run each of these SQL commands one by one:

### Users Table
```sql
CREATE TABLE users (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  phone VARCHAR(20),
  password_hash VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX users_email_idx ON users(email);
```

### Conversations Table (for chat)
```sql
CREATE TABLE conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user1_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user2_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  last_message_at TIMESTAMP
);

CREATE INDEX conversations_users_idx ON conversations(user1_id, user2_id);
```

### Messages Table (for chat)
```sql
CREATE TABLE messages (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP
);

CREATE INDEX messages_conversation_idx ON messages(conversation_id);
CREATE INDEX messages_sender_idx ON messages(sender_id);
```

### OTP Table (for authentication)
```sql
CREATE TABLE otps (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email VARCHAR(255),
  phone VARCHAR(20),
  otp_code VARCHAR(6),
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX otps_email_idx ON otps(email);
CREATE INDEX otps_phone_idx ON otps(phone);
```

---

## Step 5: Test the Connection

Run this Python script to verify connection:

```bash
cd /workspaces/96sooq-backend/backend
python3 << 'EOF'
from db.supabase_client import db

try:
    # Test connection
    result = db.select("users")
    print("✅ Successfully connected to Supabase!")
    print(f"Users count: {len(result)}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
EOF
```

---

## Step 6: Run the Server

```bash
cd /workspaces/96sooq-backend/backend
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Visit:
- **API:** http://localhost:8000
- **Swagger Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health

---

## Common Issues

### ❌ "Supabase URL and Key must be set"
- Make sure `.env` file exists and has correct values
- Check spelling and no extra spaces

### ❌ Connection refused
- Check if Supabase project is active
- Verify URL is correct (should end with `.supabase.co`)

### ❌ CORS errors from Flutter app
- Already configured in `main.py` with `allow_origins=["*"]`
- Should work automatically

---

## Next Steps

Once Supabase is connected, we'll build:
1. ✅ **Users Module** - Registration, login, user management
2. ✅ **Chat Module** - Messages and conversations
3. ✅ **OTP Module** - Phone/Email authentication

Let me know when you've completed the setup!
