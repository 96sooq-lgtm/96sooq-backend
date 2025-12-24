# Supabase Setup Quick Reference

## Quick Steps (5 minutes)

### 1. Create Project at supabase.com
```
Name: 96sooq
Region: Choose closest to you
Save the database password!
```

### 2. Get Credentials (Settings → API)
Copy these two values:
- **Project URL** → SUPABASE_URL
- **anon public key** → SUPABASE_KEY

### 3. Update .env File
```bash
cd /workspaces/96sooq-backend/backend
cp .env.example .env
# Edit .env and replace:
# SUPABASE_URL=your_url_here
# SUPABASE_KEY=your_key_here
```

### 4. Create Tables in Supabase Dashboard
Go to **SQL Editor** and run the SQL commands from `SUPABASE_SETUP_GUIDE.md`

### 5. Test Connection
```bash
cd /workspaces/96sooq-backend/backend
python3 test_supabase.py
```

### 6. Start Server
```bash
python main.py
# Visit: http://localhost:8000/docs
```

---

## Current Database Schema

```
users
  ├── id (UUID, Primary Key)
  ├── email (VARCHAR, Unique)
  ├── name (VARCHAR)
  ├── phone (VARCHAR)
  ├── password_hash (VARCHAR)
  ├── created_at (TIMESTAMP)
  └── updated_at (TIMESTAMP)

conversations
  ├── id (UUID, Primary Key)
  ├── user1_id (UUID, FK → users)
  ├── user2_id (UUID, FK → users)
  ├── created_at (TIMESTAMP)
  └── last_message_at (TIMESTAMP)

messages
  ├── id (UUID, Primary Key)
  ├── conversation_id (UUID, FK → conversations)
  ├── sender_id (UUID, FK → users)
  ├── content (TEXT)
  ├── created_at (TIMESTAMP)
  └── updated_at (TIMESTAMP)

otps
  ├── id (UUID, Primary Key)
  ├── email (VARCHAR)
  ├── phone (VARCHAR)
  ├── otp_code (VARCHAR)
  ├── expires_at (TIMESTAMP)
  └── created_at (TIMESTAMP)
```

---

## Useful Supabase Dashboard Links

After creating project:
- **SQL Editor:** Write/run SQL queries
- **Table Editor:** View data visually
- **Auth Providers:** Setup authentication
- **RLS Policies:** Security rules
- **Extensions:** Enable PostgreSQL features
- **Settings → Database:** Backups, logs

---

## Need Help?

If tests fail, check:
1. .env file exists and has correct values
2. Supabase project is active (not paused)
3. Tables are created in SQL Editor
4. URL ends with `.supabase.co`
5. API key starts with `eyJ...`

See full guide: `SUPABASE_SETUP_GUIDE.md`
